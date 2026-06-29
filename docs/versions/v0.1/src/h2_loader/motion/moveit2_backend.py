"""ROS2/MoveIt2-Bewegungsbackend (Platzhalter, spätere Ausbaustufe).

Belegt den ROS2-Umstiegspunkt: dieselbe ``MotionPlannerInterface``, dahinter
echte Bahnplanung über MoveIt2. Wird auf dem Zielsystem mit installiertem ROS2
implementiert; der ROS2-Stack ist absichtlich kein harter Import dieses Pakets
(Extra ``[ros2]``). Bis dahin sind alle Methoden Stubs.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import MotionPlannerInterface

_log = get_logger(__name__)


class MoveIt2Planner(MotionPlannerInterface):
    """MoveIt2-Bahnplanung (Stub) — Aktivierung in späterer Ausbaustufe."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        _log.warning("MoveIt2Planner instanziiert — Stub, ROS2-Anbindung folgt auf dem Zielsystem")

    def move_to(self, arm: str, pose_name: str) -> None:
        raise NotImplementedError("MoveIt2Planner.move_to: ROS2-Ausbaustufe")

    def follow(self, arm: str, trajectory: list[list[float]]) -> None:
        raise NotImplementedError("MoveIt2Planner.follow: ROS2-Ausbaustufe")
