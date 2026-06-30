"""Onboard-Locomotion: Lauf-Controller über das bordeigene SDK.

Auf dem Zielsystem über ``unitree_sdk2py.h2.loco.h2_loco_client.LocoClient``
(``Init/Start/StandUp/Move(vx,vy,ω)/SetVelocity/StopMove/Damp``). Im Stub-Stand
wird nur geloggt.

WICHTIG — velocity-/FSM-basiert, KEIN Wegpunkt-Fahren:
    Der Onboard-Controller liefert nur Geschwindigkeitsbefehle und FSM-Zustände,
    NICHT „fahre zu Station X". ``move_to(station)`` ist als Interface korrekt,
    benötigt auf dem Zielsystem aber zusätzlich eine **Lokalisierung + Pfad-/
    Regelschicht** (Ist-Pose → Soll-Pose → ``Move`` als Closed Loop) — z. B. über
    ``unilidar_sdk2`` + ``point_lio_unilidar`` oder ``unitree_ros2`` + Nav2.
    Bis dahin ist diese Klasse ein Platzhalter, der die FSM-/Velocity-Befehle
    kapseln, aber nicht autonom navigieren kann. Siehe docs/sdk_reference.md.
"""

from __future__ import annotations

from ..drivers.base import RobotDriverInterface
from ...util.config import Station
from ...util.logging import get_logger
from .base import LocomotionInterface

_log = get_logger(__name__)


class OnboardLocomotion(LocomotionInterface):
    """Lauf-Controller über den bordeigenen H2-PLUS-SDK (High-Level-Wegpunkt).

    Auf dem Zielsystem wird ``move_to`` den Onboard-Lauf-Controller über das
    SDK mit einem High-Level-Geh-/Wegpunktbefehl kommandieren. Im Stub-Stand
    loggt die Implementierung nur die Schritte.

    Args:
        stations: Mapping Stationsname -> ``Station``-Objekt mit Position.
        driver: optionaler Lowlevel-Treiber (für spätere SDK-Erweiterung);
            im Stub-Stand nicht genutzt.
    """

    def __init__(
        self,
        stations: dict[str, Station],
        driver: RobotDriverInterface | None = None,
    ) -> None:
        self._stations = stations
        self._driver = driver
        self._current: str | None = None

    def move_to(self, station: str) -> bool:
        """Lässt den Roboter zur benannten Station laufen.

        Args:
            station: Zielstation (muss in ``stations`` konfiguriert sein).

        Returns:
            True bei Erfolg.

        Raises:
            KeyError: wenn ``station`` nicht in der Stationsliste steht.
        """
        if station not in self._stations:
            verfuegbar = sorted(self._stations)
            raise KeyError(
                f"Unbekannte Station: {station!r} (verfügbar: {verfuegbar})"
            )
        pos = self._stations[station].position
        # Auf dem Zielsystem: Lokalisierung (z. B. point_lio_unilidar) liefert die Ist-Pose,
        # eine Pfad-/Regelschicht erzeugt daraus LocoClient.Move(vx, vy, omega)-Befehle bis pos.
        _log.info(
            "OnboardLocomotion: laufe zu '%s' @ position=%s (Stub)", station, pos
        )
        self._current = station
        return True

    def current_station(self) -> str | None:
        """Gibt die zuletzt angefahrene Station zurück (None = noch keine)."""
        return self._current

    def stop(self) -> None:
        """Hält die Bewegung an (Stub: nur Log)."""
        _log.warning("OnboardLocomotion: stop() — Bewegung anhalten (Stub)")
