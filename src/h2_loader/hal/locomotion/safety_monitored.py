"""Locomotion-Decorator mit funktionaler Sicherheitsüberwachung.

Umhüllt ein beliebiges ``LocomotionInterface`` und prüft vor jeder Fahrt,
ob der ``SafetySupervisor`` die Bewegung erlaubt. Bei Verweigerung wird
``inner.stop()`` aufgerufen und False zurückgegeben — der Roboter fährt nicht.

NICHT sicherheitsgerichtet — echter Personenschutz liegt in der Safety-SPS
(hardwired, zweikanalig). Diese Schicht hält nur den Softwareablauf an.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...util.logging import get_logger
from .base import LocomotionInterface

if TYPE_CHECKING:
    from ...core.safety import SafetySupervisor

_log = get_logger(__name__)


class SafetyMonitoredLocomotion(LocomotionInterface):
    """Locomotion-Wrapper, der Fahrfreigabe via ``SafetySupervisor`` prüft.

    Args:
        inner:      Das eigentliche Locomotion-Backend (z. B. OnboardLocomotion).
        supervisor: Supervisor-Instanz für die Freigabeprüfung.
    """

    def __init__(self, inner: LocomotionInterface, supervisor: SafetySupervisor) -> None:
        self._inner = inner
        self._supervisor = supervisor

    def move_to(self, station: str) -> bool:
        """Fährt zur Station, wenn der Supervisor die Fahrt erlaubt.

        Args:
            station: Zielstation.

        Returns:
            False, wenn die Fahrt verweigert wurde; sonst Ergebnis des inneren
            Locomotion-Backends.
        """
        if not self._supervisor.allow_move_to(station):
            _log.error(
                "SafetyMonitoredLocomotion: Fahrt nach '%s' verweigert — Supervisor blockiert",
                station,
            )
            self._inner.stop()
            return False
        return self._inner.move_to(station)

    def current_station(self) -> str | None:
        """Delegiert an das innere Backend."""
        return self._inner.current_station()

    def stop(self) -> None:
        """Delegiert Stoppbefehl an das innere Backend."""
        self._inner.stop()
