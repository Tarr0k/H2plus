"""Interface für das Locomotion-Backend (Navigation / Laufen).

Der gesamte Ablaufcode (Skills, Core) ruft ausschließlich
``LocomotionInterface``. Heute liefert ``OnboardLocomotion`` die Bewegung über
den bordeigenen Lauf-Controller des H2 PLUS (SDK-High-Level-Wegpunktbefehle);
später kann z. B. eine RL-Policy oder ein ROS2-Nav2-Planner registriert werden,
ohne dass ein Skill geändert wird (analog ``MotionPlannerInterface`` / ADR-Muster).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LocomotionInterface(ABC):
    """Abstraktes Locomotion-Backend: Stationen anfahren / Position abfragen / stoppen.

    Ablaufcode ruft nur dieses Interface; das Backend heute ist
    ``OnboardLocomotion`` (SDK-High-Level), später austauschbar gegen z. B.
    eine RL-Policy (ADR-0004) oder einen ROS2-Nav2-Planner.
    """

    @abstractmethod
    def move_to(self, station: str) -> bool:
        """Lässt den ganzen Roboter zur benannten Station laufen.

        Args:
            station: Name der Zielstation (muss in der konfigurierten
                Stationsliste vorhanden sein).

        Returns:
            True bei erfolgreichem Erreichen der Station.

        Raises:
            KeyError: wenn ``station`` nicht bekannt ist.
        """

    @abstractmethod
    def current_station(self) -> str | None:
        """Gibt die zuletzt erfolgreich erreichte Station zurück.

        Returns:
            Stations-Name oder None, wenn noch keine Station angefahren wurde.
        """

    @abstractmethod
    def stop(self) -> None:
        """Hält die laufende Bewegung sofort an (Notfall- oder Interruptpfad)."""
