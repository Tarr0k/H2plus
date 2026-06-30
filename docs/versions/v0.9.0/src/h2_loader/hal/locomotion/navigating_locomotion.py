"""Closed-Loop-Navigationregler für den H2 PLUS.

Realisiert ``move_to(station)`` als velocity-basierten P-Regler:
  - Ist-Pose kommt von ``LocalizationInterface`` (Sim: Odometrie-Integration;
    Ziel: LiDAR + ``point_lio_unilidar``).
  - Stellgröße geht an ``VelocitySink`` (Sim: direkte Integration; Ziel:
    ``LocoClient.Move``).

Keine Hindernisvermeidung; holonomisches Kinematikmodell (zu verifizieren
am Zielsystem). Siehe auch docs/sdk_reference.md, ADR-0004-Nachtrag.
"""

from __future__ import annotations

import math
from typing import Any

from ...util.config import Station
from ...util.logging import get_logger
from .base import LocomotionInterface
from .localization import LocalizationInterface, wrap_angle
from .velocity_sink import VelocitySink

_log = get_logger(__name__)

# Standardparameter des Reglers — überschreibbar per nav-Dict aus stations.yaml.
_NAV_DEFAULTS: dict[str, float] = {
    "max_linear": 0.5,    # m/s — maximale Translationsgeschwindigkeit
    "max_angular": 0.8,   # rad/s — maximale Winkelgeschwindigkeit
    "kp_linear": 1.0,     # P-Verstärkung für Translation
    "kp_angular": 1.5,    # P-Verstärkung für Rotation
    "tol_xy": 0.05,       # m — Positionstoleranz
    "tol_theta": 0.05,    # rad — Orientierungstoleranz
    "dt": 0.1,            # s — Regeltakt (10 Hz)
    "max_steps": 2000,    # Schritte bis Timeout-Abbruch
}


def _clamp(value: float, lo: float, hi: float) -> float:
    """Begrenzt ``value`` auf [lo, hi]."""
    return max(lo, min(hi, value))


class NavigatingLocomotion(LocomotionInterface):
    """Velocity-basierter Closed-Loop-Navigationregler.

    Ruft in jedem Schritt die Ist-Pose ab, berechnet den Lagefehler und erzeugt
    daraus per P-Regler einen Body-Frame-Geschwindigkeitsbefehl, der an den
    ``VelocitySink`` gesendet wird.

    In der Simulation liefert ``SimLocalization`` perfekte Odometrie und
    ``SimVelocitySink`` integriert die Pose kinematisch. Am Zielsystem ersetzt
    LiDAR-Odometrie (``unilidar_sdk2`` + ``point_lio_unilidar``) die
    Lokalisierung und ``LocoClientVelocitySink`` sendet an ``LocoClient.Move``.

    Keine Hindernisvermeidung. Holonomisches Fahrzeugmodell (zu verifizieren
    am Zielsystem). Siehe docs/sdk_reference.md, ADR-0004-Nachtrag.

    Args:
        stations:     Mapping Stationsname -> ``Station``-Objekt.
        localization: Aktuelle Roboterpose (Interface).
        sink:         Empfänger der Geschwindigkeitsbefehle.
        nav:          Optionale Regler-Parameter; fehlende Schlüssel werden aus
                      ``_NAV_DEFAULTS`` ergänzt.
    """

    def __init__(
        self,
        stations: dict[str, Station],
        localization: LocalizationInterface,
        sink: VelocitySink,
        nav: dict[str, Any] | None = None,
    ) -> None:
        self._stations = stations
        self._loc = localization
        self._sink = sink
        self._current: str | None = None

        cfg = dict(_NAV_DEFAULTS)
        if nav:
            cfg.update(nav)

        self._max_linear: float = float(cfg["max_linear"])
        self._max_angular: float = float(cfg["max_angular"])
        self._kp_linear: float = float(cfg["kp_linear"])
        self._kp_angular: float = float(cfg["kp_angular"])
        self._tol_xy: float = float(cfg["tol_xy"])
        self._tol_theta: float = float(cfg["tol_theta"])
        self._dt: float = float(cfg["dt"])
        self._max_steps: int = int(cfg["max_steps"])

    def move_to(self, station: str) -> bool:
        """Fährt den Roboter per Closed-Loop-Regler zur benannten Station.

        Args:
            station: Zielstation (muss in ``stations`` konfiguriert sein).

        Returns:
            True, wenn die Station innerhalb von ``max_steps`` erreicht wurde.
            False bei Timeout.

        Raises:
            KeyError: wenn ``station`` nicht in der Stationsliste steht.
        """
        if station not in self._stations:
            verfuegbar = sorted(self._stations)
            raise KeyError(
                f"Unbekannte Station: {station!r} (verfügbar: {verfuegbar})"
            )

        target = self._stations[station].position  # [x, y, theta]
        tx, ty, ttheta = float(target[0]), float(target[1]), float(target[2])

        _log.info(
            "NavigatingLocomotion: starte Fahrt nach '%s' @ (%.2f, %.2f, %.2f rad)",
            station, tx, ty, ttheta,
        )

        for step in range(self._max_steps):
            p = self._loc.current_pose()
            ex = tx - p.x
            ey = ty - p.y
            etheta = wrap_angle(ttheta - p.theta)

            if math.hypot(ex, ey) < self._tol_xy and abs(etheta) < self._tol_theta:
                self._sink.stop()
                self._current = station
                _log.info(
                    "NavigatingLocomotion: Station '%s' erreicht nach %d Schritten "
                    "(pos=(%.3f, %.3f), theta=%.3f rad)",
                    station, step + 1, p.x, p.y, p.theta,
                )
                return True

            # Lagefehler in den Body-Frame drehen
            cos_t = math.cos(p.theta)
            sin_t = math.sin(p.theta)
            vx_b = cos_t * ex + sin_t * ey
            vy_b = -sin_t * ex + cos_t * ey

            # P-Regler + Begrenzung
            vx = _clamp(self._kp_linear * vx_b, -self._max_linear, self._max_linear)
            vy = _clamp(self._kp_linear * vy_b, -self._max_linear, self._max_linear)
            omega = _clamp(self._kp_angular * etheta, -self._max_angular, self._max_angular)

            self._sink.send_velocity(vx, vy, omega)

        # Timeout
        self._sink.stop()
        p = self._loc.current_pose()
        _log.warning(
            "NavigatingLocomotion: Ziel nicht erreicht — Station '%s' nach %d Schritten "
            "(pos=(%.3f, %.3f), theta=%.3f rad)",
            station, self._max_steps, p.x, p.y, p.theta,
        )
        return False

    def current_station(self) -> str | None:
        """Gibt die zuletzt erfolgreich angefahrene Station zurück.

        Returns:
            Stationsname oder None, wenn noch keine Station erreicht wurde.
        """
        return self._current

    def stop(self) -> None:
        """Sendet sofort einen Stop-Befehl an den Velocity-Sink."""
        self._sink.stop()
