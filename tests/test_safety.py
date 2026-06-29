"""Tests für SafetySupervisor und SafetyMonitoredLocomotion.

Abgedeckte Szenarien:
  - SafetySupervisor ohne Handshake: Basis-NOT-AUS + Reset.
  - allow_move_to: freie/belegte Zonen, robot_allowed, unbekannte Station.
  - SafetySupervisor mit Handshake: robotEnable, estopFromPlc, watchdogFault.
  - evaluate_heartbeat: Watchdog-Logik.
  - SafetyMonitoredLocomotion: blockierter und erlaubter move_to.
"""

from __future__ import annotations

import pytest

from h2_loader.core.safety import SafetySupervisor
from h2_loader.hal.locomotion.onboard_locomotion import OnboardLocomotion
from h2_loader.hal.locomotion.safety_monitored import SafetyMonitoredLocomotion
from h2_loader.plc.handshake import H2HandshakeClient
from h2_loader.util.config import SafetyZone, Station


# ---------------------------------------------------------------------------
# Hilfsfixtures
# ---------------------------------------------------------------------------

def _make_zones() -> dict[str, SafetyZone]:
    return {
        "transit":      SafetyZone("transit",      speed_limit=0.8, robot_allowed=True),
        "machine_zone": SafetyZone("machine_zone", speed_limit=0.3, robot_allowed=True),
        "no_go_zone":   SafetyZone("no_go_zone",   speed_limit=0.0, robot_allowed=False),
    }


def _make_station_zone() -> dict[str, str]:
    return {
        "home":    "transit",
        "machine": "machine_zone",
        "danger":  "no_go_zone",
    }


def _make_stations() -> dict[str, Station]:
    return {
        "home":    Station("home",    [0.0, 0.0, 0.0]),
        "machine": Station("machine", [0.0, 2.0, 0.0]),
        "danger":  Station("danger",  [5.0, 5.0, 0.0]),
    }


# ---------------------------------------------------------------------------
# SafetySupervisor ohne Handshake
# ---------------------------------------------------------------------------

class TestSafetySupervisorBase:
    """Basisprüfungen ohne SPS-Handshake."""

    def test_is_clear_default(self) -> None:
        sup = SafetySupervisor()
        assert sup.is_clear() is True

    def test_trigger_emergency_stop(self) -> None:
        sup = SafetySupervisor()
        sup.trigger_emergency_stop()
        assert sup.is_clear() is False

    def test_reset_after_estop(self) -> None:
        sup = SafetySupervisor()
        sup.trigger_emergency_stop()
        sup.reset()
        assert sup.is_clear() is True


# ---------------------------------------------------------------------------
# allow_move_to (ohne Handshake)
# ---------------------------------------------------------------------------

class TestAllowMoveTo:
    """Zonenprüfungen für allow_move_to."""

    def test_free_allowed_zone(self) -> None:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        assert sup.allow_move_to("home") is True

    def test_occupied_zone_denied(self) -> None:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        sup.set_zone_occupied("transit", True)
        assert sup.allow_move_to("home") is False

    def test_robot_not_allowed_zone(self) -> None:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        assert sup.allow_move_to("danger") is False

    def test_unknown_station_denied(self) -> None:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        assert sup.allow_move_to("nonexistent") is False

    def test_after_estop_denied(self) -> None:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        sup.trigger_emergency_stop()
        assert sup.allow_move_to("home") is False

    def test_zone_free_again_after_clear(self) -> None:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        sup.set_zone_occupied("transit", True)
        sup.set_zone_occupied("transit", False)
        assert sup.allow_move_to("home") is True


# ---------------------------------------------------------------------------
# SafetySupervisor mit Handshake
# ---------------------------------------------------------------------------

class TestSafetySupervisorWithHandshake:
    """Prüft, dass Safety-UDT-Member korrekt ausgewertet werden."""

    @pytest.fixture
    def handshake(self) -> H2HandshakeClient:
        hs = H2HandshakeClient()
        # Standardmäßig robotEnable=False (Kaltstart-Default)
        return hs

    def test_robot_enable_false_blocks(self, handshake: H2HandshakeClient) -> None:
        sup = SafetySupervisor(handshake=handshake)
        # robotEnable ist per Default False → nicht frei
        assert sup.is_clear() is False

    def test_robot_enable_true_clears(self, handshake: H2HandshakeClient) -> None:
        handshake.write("safety", "robotEnable", True)
        sup = SafetySupervisor(handshake=handshake)
        assert sup.is_clear() is True

    def test_estop_from_plc_blocks(self, handshake: H2HandshakeClient) -> None:
        handshake.write("safety", "robotEnable", True)
        handshake.write("safety", "estopFromPlc", True)
        sup = SafetySupervisor(handshake=handshake)
        assert sup.is_clear() is False

    def test_watchdog_fault_blocks(self, handshake: H2HandshakeClient) -> None:
        handshake.write("safety", "robotEnable", True)
        handshake.write("safety", "watchdogFault", True)
        sup = SafetySupervisor(handshake=handshake)
        assert sup.is_clear() is False


# ---------------------------------------------------------------------------
# evaluate_heartbeat
# ---------------------------------------------------------------------------

class TestEvaluateHeartbeat:
    """Watchdog-Logik: gleicher Heartbeat → watchdogFault; geänderter → kein Fault."""

    @pytest.fixture
    def handshake(self) -> H2HandshakeClient:
        hs = H2HandshakeClient()
        hs.write("safety", "robotEnable", True)
        hs.write("control", "plcHeartbeat", 42)
        return hs

    def test_stale_heartbeat_sets_fault(self, handshake: H2HandshakeClient) -> None:
        sup = SafetySupervisor(handshake=handshake)
        sup.evaluate_heartbeat()  # erster Aufruf: _last_heartbeat=42, stale_count=0
        sup.evaluate_heartbeat()  # zweiter: gleich → stale_count=1; kein Fault noch
        sup.evaluate_heartbeat()  # dritter: stale_count=2 → watchdogFault=True
        assert bool(handshake.read("safety", "watchdogFault")) is True

    def test_changing_heartbeat_clears_fault(self, handshake: H2HandshakeClient) -> None:
        sup = SafetySupervisor(handshake=handshake)
        # Stale-Zustand herbeiführen
        sup.evaluate_heartbeat()
        sup.evaluate_heartbeat()
        sup.evaluate_heartbeat()
        assert bool(handshake.read("safety", "watchdogFault")) is True
        # Heartbeat ändert sich → Fault wird zurückgesetzt
        handshake.write("control", "plcHeartbeat", 43)
        sup.evaluate_heartbeat()
        assert bool(handshake.read("safety", "watchdogFault")) is False

    def test_two_calls_same_value_no_fault_yet(self, handshake: H2HandshakeClient) -> None:
        """Erst nach dem dritten gleichen Wert (stale_count >= 2) wird Fault gesetzt."""
        sup = SafetySupervisor(handshake=handshake)
        sup.evaluate_heartbeat()  # stale_count=0 (erster Aufruf, last=None→42)
        sup.evaluate_heartbeat()  # stale_count=1
        assert bool(handshake.read("safety", "watchdogFault")) is False


# ---------------------------------------------------------------------------
# SafetyMonitoredLocomotion
# ---------------------------------------------------------------------------

class TestSafetyMonitoredLocomotion:
    """Prüft Delegation und Blockierung der Locomotion."""

    @pytest.fixture
    def setup(self) -> tuple[SafetySupervisor, SafetyMonitoredLocomotion]:
        sup = SafetySupervisor(zones=_make_zones(), station_zone=_make_station_zone())
        inner = OnboardLocomotion(_make_stations())
        wrapped = SafetyMonitoredLocomotion(inner, sup)
        return sup, wrapped

    def test_blocked_move_returns_false(
        self, setup: tuple[SafetySupervisor, SafetyMonitoredLocomotion]
    ) -> None:
        sup, wrapped = setup
        sup.set_zone_occupied("transit", True)
        result = wrapped.move_to("home")
        assert result is False

    def test_blocked_move_station_unchanged(
        self, setup: tuple[SafetySupervisor, SafetyMonitoredLocomotion]
    ) -> None:
        sup, wrapped = setup
        sup.set_zone_occupied("transit", True)
        wrapped.move_to("home")
        # current_station soll sich nicht geändert haben
        assert wrapped.current_station() is None

    def test_allowed_move_delegates(
        self, setup: tuple[SafetySupervisor, SafetyMonitoredLocomotion]
    ) -> None:
        _, wrapped = setup
        result = wrapped.move_to("home")
        assert result is True
        assert wrapped.current_station() == "home"

    def test_allowed_move_then_blocked(
        self, setup: tuple[SafetySupervisor, SafetyMonitoredLocomotion]
    ) -> None:
        sup, wrapped = setup
        wrapped.move_to("home")
        assert wrapped.current_station() == "home"
        sup.set_zone_occupied("machine_zone", True)
        result = wrapped.move_to("machine")
        assert result is False
        # Station bleibt auf "home"
        assert wrapped.current_station() == "home"
