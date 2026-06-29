"""Sicherheits-/Freigabelogik.

Bündelt Not-Aus, Freigabe und funktionale Zonenüberwachung.

WICHTIG — KEINE SICHERHEITSGERICHTETE SCHICHT:
    Diese Schicht ist NICHT sicherheitsgerichtet. Funktionale Sicherheit und
    Personenschutz sind hardwired (Safety-SPS, F-Signale, sichere Sensorik).
    ``SafetyGate`` und ``SafetySupervisor`` fordern nur sichere Zustände an
    und halten den Softwareablauf an — sie ersetzen NICHT den zertifizierten
    Sicherheitskreis der Anlage.

Klassen:
    SafetyGate:       Basis-Freigabe (NOT-AUS-Flag, Backward-Compat).
    SafetySupervisor: Erweiterter Supervisor mit Zonen- und Handshake-Checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..util.config import SafetyZone
from ..util.logging import get_logger

if TYPE_CHECKING:
    from ..plc.handshake import H2HandshakeClient

_log = get_logger(__name__)


class SafetyGate:
    """Software-seitige Freigabe vor Bewegungsaktionen (kein Ersatz für den SPS-Sicherheitskreis)."""

    def __init__(self) -> None:
        self._emergency_stop = False

    def trigger_emergency_stop(self) -> None:
        _log.error("SafetyGate: NOT-AUS ausgelöst")
        self._emergency_stop = True

    def reset(self) -> None:
        _log.info("SafetyGate: zurückgesetzt")
        self._emergency_stop = False

    def is_clear(self) -> bool:
        """True, wenn keine Sicherheitsverriegelung aktiv ist."""
        return not self._emergency_stop


class SafetySupervisor(SafetyGate):
    """Funktionaler Sicherheits-Supervisor mit Zonen- und Handshake-Checks.

    NICHT sicherheitsgerichtet — siehe Modul-Docstring.

    Prüft vor jeder Fahrbewegung:
      - Software-NOT-AUS (geerbt von SafetyGate)
      - SPS-seitige Safety-Member (estopFromPlc, robotEnable, watchdogFault …)
      - Zonen-Besetzung und robot_allowed-Flag

    Args:
        handshake:    H2-Handshake-Client; None = kein SPS-Check.
        zones:        Mapping Zonenname -> SafetyZone (aus safety_zones.yaml).
        station_zone: Mapping Stationsname -> Zonenname.
    """

    def __init__(
        self,
        handshake: H2HandshakeClient | None = None,
        zones: dict[str, SafetyZone] | None = None,
        station_zone: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self._handshake = handshake
        self._zones: dict[str, SafetyZone] = zones if zones is not None else {}
        self._station_zone: dict[str, str] = station_zone if station_zone is not None else {}
        # Laufzeit-Belegungszustand je Zone (initialisiert aus SafetyZone.occupied)
        self._occupied: dict[str, bool] = {z: self._zones[z].occupied for z in self._zones}
        self._last_heartbeat: int | None = None
        self._stale_count: int = 0

    # ------------------------------------------------------------------
    # Freigabe-Check
    # ------------------------------------------------------------------

    def is_clear(self) -> bool:
        """True, wenn weder NOT-AUS noch SPS-Safety-Verriegelung aktiv ist.

        Prüft (falls handshake gesetzt):
          - estopFromPlc / estopFromRobot dürfen nicht True sein.
          - robotEnable muss True sein.
          - watchdogFault darf nicht True sein.
        """
        base = super().is_clear()
        if self._handshake is None:
            return base
        estop_plc   = bool(self._handshake.read("safety", "estopFromPlc"))
        estop_robot = bool(self._handshake.read("safety", "estopFromRobot"))
        robot_en    = bool(self._handshake.read("safety", "robotEnable"))
        wdog_fault  = bool(self._handshake.read("safety", "watchdogFault"))
        cond = (not estop_plc) and (not estop_robot) and robot_en and (not wdog_fault)
        return base and cond

    # ------------------------------------------------------------------
    # Zonen-API
    # ------------------------------------------------------------------

    def set_zone_occupied(self, zone: str, value: bool) -> None:
        """Setzt den Belegungs-Status einer Zone.

        Args:
            zone:  Zonenname (muss in zones konfiguriert sein).
            value: True = Zone belegt, False = frei.
        """
        self._occupied[zone] = value
        _log.debug("SafetySupervisor: Zone '%s' besetzt=%s", zone, value)

    def allow_move_to(self, station: str) -> bool:
        """True, wenn der Roboter die Zielstation anfahren darf.

        Bedingungen:
          - is_clear() muss True sein.
          - Station muss einer bekannten Zone zugeordnet sein.
          - Zone muss robot_allowed=True haben.
          - Zone darf nicht besetzt sein.

        Args:
            station: Zielstationsname.
        """
        if not self.is_clear():
            _log.warning("SafetySupervisor: allow_move_to('%s') verweigert — nicht frei", station)
            return False
        zone_name = self._station_zone.get(station)
        if zone_name is None or zone_name not in self._zones:
            _log.warning(
                "SafetySupervisor: allow_move_to('%s') verweigert — unbekannte Station/Zone", station
            )
            return False
        zone = self._zones[zone_name]
        if not zone.robot_allowed:
            _log.warning(
                "SafetySupervisor: allow_move_to('%s') verweigert — Zone '%s' nicht für Roboter freigegeben",
                station,
                zone_name,
            )
            return False
        if self._occupied.get(zone_name, False):
            _log.warning(
                "SafetySupervisor: allow_move_to('%s') verweigert — Zone '%s' besetzt",
                station,
                zone_name,
            )
            return False
        return True

    def speed_limit(self, station: str) -> float:
        """Gibt das Geschwindigkeitslimit für die Zielstation zurück.

        Returns:
            0.0, wenn die Fahrt nicht erlaubt ist; sonst speed_limit der Zone.
        """
        if not self.allow_move_to(station):
            return 0.0
        zone_name = self._station_zone[station]
        return self._zones[zone_name].speed_limit

    # ------------------------------------------------------------------
    # Watchdog
    # ------------------------------------------------------------------

    def evaluate_heartbeat(self) -> None:
        """Prüft, ob der SPS-Heartbeat noch läuft (funktionaler Watchdog).

        Liest ``control.plcHeartbeat``; bleibt der Wert über zwei aufeinander-
        folgende Aufrufe gleich, wird ``watchdogFault`` auf True gesetzt —
        ansonsten auf False.

        Hinweis: Diese Methode ist von ``is_clear()`` entkoppelt, damit
        ``is_clear()`` idempotent bleibt.
        """
        if self._handshake is None:
            return
        current_hb = int(self._handshake.read("control", "plcHeartbeat"))
        if current_hb == self._last_heartbeat:
            self._stale_count += 1
        else:
            self._stale_count = 0
        self._last_heartbeat = current_hb
        fault = self._stale_count >= 2
        self._handshake.write("safety", "watchdogFault", fault)
        if fault:
            _log.error(
                "SafetySupervisor: SPS-Heartbeat steht — watchdogFault gesetzt (stale_count=%d)",
                self._stale_count,
            )
