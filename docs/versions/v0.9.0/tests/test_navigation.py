"""Tests für die Lokalisierungs-/Navigationsschicht (v0.9.0).

Abgedeckt:
- SimLocalization.integrate: kinematische Integration, wrap_angle.
- NavigatingLocomotion: Ziel erreichen, Mehrstufig, unbekannte Station, max_steps-Guard.
"""

from __future__ import annotations

import math

import pytest

from h2_loader.hal.locomotion.localization import Pose2D, SimLocalization, wrap_angle
from h2_loader.hal.locomotion.navigating_locomotion import NavigatingLocomotion
from h2_loader.hal.locomotion.velocity_sink import SimVelocitySink
from h2_loader.util.config import Station

# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def _approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# Kleine Stationskarte nur für Navigations-Tests (unabhängig von config/)
# ---------------------------------------------------------------------------

_NAV_STATIONS: dict[str, Station] = {
    "home":    Station("home",    [0.0, 0.0, 0.0],  "Parkposition"),
    "machine": Station("machine", [1.0, 0.0, 0.0],  "Maschine"),
    "depot":   Station("depot",   [1.0, 1.0, 1.57], "Depot"),
}

# Regler-Parameter: kleiner dt für schnellere Tests, ausreichende max_steps.
_NAV_PARAMS: dict = {
    "max_linear": 0.5,
    "max_angular": 0.8,
    "kp_linear": 1.0,
    "kp_angular": 1.5,
    "tol_xy": 0.05,
    "tol_theta": 0.05,
    "dt": 0.05,
    "max_steps": 5000,
}


# ---------------------------------------------------------------------------
# wrap_angle
# ---------------------------------------------------------------------------

class TestWrapAngle:
    def test_null(self) -> None:
        assert _approx(wrap_angle(0.0), 0.0)

    def test_pi_bleibt_pi(self) -> None:
        # pi → pi (Grenzfall: (-pi, pi] → pi ist enthalten)
        assert _approx(wrap_angle(math.pi), math.pi)

    def test_minus_pi_wird_pi(self) -> None:
        # -pi liegt außerhalb (-pi, pi]; soll zu +pi werden
        assert _approx(wrap_angle(-math.pi), math.pi)

    def test_ueberroll_positiv(self) -> None:
        # 3*pi/2 → -pi/2
        assert _approx(wrap_angle(3 * math.pi / 2), -math.pi / 2, tol=1e-9)

    def test_ueberroll_negativ(self) -> None:
        # -3*pi/2 → pi/2
        assert _approx(wrap_angle(-3 * math.pi / 2), math.pi / 2, tol=1e-9)

    def test_bereich_bleibt_erhalten(self) -> None:
        for a in [-2 * math.pi, -math.pi + 0.001, 0.0, math.pi - 0.001, 2 * math.pi]:
            w = wrap_angle(a)
            assert -math.pi < w <= math.pi, f"wrap_angle({a}) = {w} außerhalb (-pi, pi]"


# ---------------------------------------------------------------------------
# SimLocalization.integrate
# ---------------------------------------------------------------------------

class TestSimLocalization:
    def test_startpose_default(self) -> None:
        """Ohne Startpose beginnt der Roboter in (0, 0, 0)."""
        loc = SimLocalization()
        p = loc.current_pose()
        assert _approx(p.x, 0.0) and _approx(p.y, 0.0) and _approx(p.theta, 0.0)

    def test_startpose_gesetzt(self) -> None:
        """Mit expliziter Startpose beginnt der Roboter dort."""
        loc = SimLocalization(Pose2D(x=1.0, y=2.0, theta=0.5))
        p = loc.current_pose()
        assert _approx(p.x, 1.0) and _approx(p.y, 2.0) and _approx(p.theta, 0.5)

    def test_integrate_vorwaerts_theta0(self) -> None:
        """Vorwärtsfahrt (vx=1) bei theta=0 → x wächst um 1."""
        loc = SimLocalization()
        loc.integrate(vx=1.0, vy=0.0, omega=0.0, dt=1.0)
        p = loc.current_pose()
        assert _approx(p.x, 1.0, tol=1e-9)
        assert _approx(p.y, 0.0, tol=1e-9)

    def test_integrate_vorwaerts_nach_drehung(self) -> None:
        """Nach Drehung um pi/2 (theta=pi/2) wächst bei vx=1 das y."""
        loc = SimLocalization(Pose2D(theta=math.pi / 2))
        loc.integrate(vx=1.0, vy=0.0, omega=0.0, dt=1.0)
        p = loc.current_pose()
        assert _approx(p.x, 0.0, tol=1e-9)
        assert _approx(p.y, 1.0, tol=1e-9)

    def test_integrate_seitwärts(self) -> None:
        """Seitwärtsfahrt (vy=1) bei theta=0 → y wächst um 1."""
        loc = SimLocalization()
        loc.integrate(vx=0.0, vy=1.0, omega=0.0, dt=1.0)
        p = loc.current_pose()
        assert _approx(p.x, 0.0, tol=1e-9)
        assert _approx(p.y, 1.0, tol=1e-9)

    def test_integrate_rotation(self) -> None:
        """Rotation um omega dt → theta aktualisiert sich."""
        loc = SimLocalization()
        loc.integrate(vx=0.0, vy=0.0, omega=1.0, dt=1.0)
        p = loc.current_pose()
        assert _approx(p.theta, 1.0, tol=1e-9)

    def test_integrate_wrap_angle(self) -> None:
        """Theta wird nach Integration in (-pi, pi] gehalten."""
        loc = SimLocalization(Pose2D(theta=math.pi - 0.1))
        loc.integrate(vx=0.0, vy=0.0, omega=1.0, dt=1.0)
        p = loc.current_pose()
        assert -math.pi < p.theta <= math.pi

    def test_current_pose_gibt_kopie(self) -> None:
        """current_pose() gibt eine Kopie zurück — Veränderungen haben keinen Effekt."""
        loc = SimLocalization(Pose2D(x=1.0))
        p = loc.current_pose()
        p.x = 999.0
        assert _approx(loc.current_pose().x, 1.0)


# ---------------------------------------------------------------------------
# NavigatingLocomotion
# ---------------------------------------------------------------------------

def _make_nav(stations: dict[str, Station] | None = None,
              start: Pose2D | None = None,
              nav_params: dict | None = None) -> NavigatingLocomotion:
    """Hilfsfunktion: erzeugt NavigatingLocomotion + SimLocalization + SimVelocitySink."""
    s = stations if stations is not None else _NAV_STATIONS
    params = nav_params if nav_params is not None else _NAV_PARAMS
    loc = SimLocalization(start)
    sink = SimVelocitySink(loc, dt=float(params.get("dt", 0.05)))
    return NavigatingLocomotion(s, loc, sink, nav=params)


class TestNavigatingLocomotion:
    def test_initial_current_station_none(self) -> None:
        """Vor dem ersten move_to ist current_station() None."""
        nav = _make_nav()
        assert nav.current_station() is None

    def test_move_to_machine_returns_true(self) -> None:
        """move_to('machine') von home → True."""
        nav = _make_nav()
        result = nav.move_to("machine")
        assert result is True

    def test_move_to_setzt_current_station(self) -> None:
        """Nach erfolgreicher Fahrt zeigt current_station die Zielstation."""
        nav = _make_nav()
        nav.move_to("machine")
        assert nav.current_station() == "machine"

    def test_endpose_nahe_ziel(self) -> None:
        """Endpose liegt innerhalb tol_xy/tol_theta des Ziels."""
        loc = SimLocalization()
        sink = SimVelocitySink(loc, dt=float(_NAV_PARAMS["dt"]))
        nav = NavigatingLocomotion(_NAV_STATIONS, loc, sink, nav=_NAV_PARAMS)
        nav.move_to("machine")
        p = loc.current_pose()
        ziel = _NAV_STATIONS["machine"].position
        assert math.hypot(p.x - ziel[0], p.y - ziel[1]) < _NAV_PARAMS["tol_xy"]
        assert abs(wrap_angle(ziel[2] - p.theta)) < _NAV_PARAMS["tol_theta"]

    def test_mehrstufig_zwei_stationen(self) -> None:
        """Nacheinander zwei Stationen anfahren — beide werden erreicht."""
        loc = SimLocalization()
        sink = SimVelocitySink(loc, dt=float(_NAV_PARAMS["dt"]))
        nav = NavigatingLocomotion(_NAV_STATIONS, loc, sink, nav=_NAV_PARAMS)

        assert nav.move_to("machine") is True
        p1 = loc.current_pose()
        z1 = _NAV_STATIONS["machine"].position
        assert math.hypot(p1.x - z1[0], p1.y - z1[1]) < _NAV_PARAMS["tol_xy"]

        assert nav.move_to("depot") is True
        p2 = loc.current_pose()
        z2 = _NAV_STATIONS["depot"].position
        assert math.hypot(p2.x - z2[0], p2.y - z2[1]) < _NAV_PARAMS["tol_xy"]

    def test_mehrstufig_current_station_folgt_letzter(self) -> None:
        """current_station folgt immer der zuletzt angefahrenen Station."""
        nav = _make_nav()
        nav.move_to("machine")
        assert nav.current_station() == "machine"
        nav.move_to("depot")
        assert nav.current_station() == "depot"

    def test_unbekannte_station_key_error(self) -> None:
        """move_to mit unbekanntem Namen löst KeyError aus."""
        nav = _make_nav()
        with pytest.raises(KeyError, match="nicht_vorhanden"):
            nav.move_to("nicht_vorhanden")

    def test_key_error_enthaelt_verfuegbare_stationen(self) -> None:
        """Der KeyError-Text enthält mindestens einen bekannten Stationsnamen."""
        nav = _make_nav()
        with pytest.raises(KeyError) as exc_info:
            nav.move_to("xyz")
        # 'machine' muss im Fehlertext erscheinen
        assert "machine" in str(exc_info.value)

    def test_max_steps_guard_gibt_false_zurueck(self) -> None:
        """Mit max_steps=1 und entferntem Ziel gibt move_to False zurück (kein Hängen)."""
        stationen: dict[str, Station] = {
            "home":   Station("home",   [0.0, 0.0, 0.0], "Start"),
            "fern":   Station("fern",   [100.0, 100.0, 0.0], "Weit weg"),
        }
        params = dict(_NAV_PARAMS)
        params["max_steps"] = 1
        nav = _make_nav(stations=stationen, nav_params=params)
        result = nav.move_to("fern")
        assert result is False

    def test_stop_delegiert_an_sink(self) -> None:
        """stop() löst keinen Fehler aus und kann jederzeit aufgerufen werden."""
        nav = _make_nav()
        nav.stop()  # kein Fehler erwartet

    def test_ziel_gleich_startpose_wird_sofort_erreicht(self) -> None:
        """Wenn Startpose bereits im Toleranzbereich liegt, sofort True."""
        stationen: dict[str, Station] = {
            "home": Station("home", [0.0, 0.0, 0.0], "Parkposition"),
        }
        nav = _make_nav(stations=stationen, start=Pose2D(0.0, 0.0, 0.0))
        result = nav.move_to("home")
        assert result is True
        assert nav.current_station() == "home"
