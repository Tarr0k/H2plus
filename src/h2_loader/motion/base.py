"""Interface für das Bewegungs-Backend.

Der gesamte Ablaufcode (skills, core) ruft ausschließlich ``MotionPlannerInterface``.
Heute liefert ``TeachReplayPlanner`` die Bewegung durch Abfahren angelernter
Posen; später kann ``MoveIt2Planner`` mit echter Bahnplanung registriert werden,
ohne dass ein Skill geändert wird (siehe ADR-0003).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MotionPlannerInterface(ABC):
    """Abstraktes Bewegungs-Backend: Pose anfahren / Trajektorie abfahren."""

    @abstractmethod
    def move_to(self, arm: str, pose_name: str) -> None:
        """Fährt den Arm ("left"/"right") auf die benannte (angelernte) Pose."""

    @abstractmethod
    def follow(self, arm: str, trajectory: list[list[float]]) -> None:
        """Fährt eine Folge von Gelenk-Wegpunkten [rad] für den Arm ab."""
