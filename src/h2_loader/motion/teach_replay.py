"""Teach-&-Replay-Bewegungsbackend (erster Ausbau).

Fährt fest angelernte Posen ab. Die Posen liegen als YAML in ``config/poses/``
(Gelenkwinkel je Arm) und werden hier nach Namen aufgelöst und über die HAL
(``Arm.move_joints``) ausgeführt. Bewusst ohne Bahnplanung — der Roboter fährt
Punkt-zu-Punkt die geteachten Stützstellen.
"""

from __future__ import annotations

from pathlib import Path

from ..hal.robot import Robot
from ..util.config import Pose
from ..util.logging import get_logger
from .base import MotionPlannerInterface

_log = get_logger(__name__)


class TeachReplayPlanner(MotionPlannerInterface):
    """Bewegung durch Abfahren angelernter Posen.

    Args:
        robot: HAL-Fassade, über die die Gelenke gestellt werden.
        poses_dir: Verzeichnis mit ``<pose_name>.yaml``-Dateien.
    """

    def __init__(self, robot: Robot, poses_dir: str | Path) -> None:
        self._robot = robot
        self._poses_dir = Path(poses_dir)
        self._cache: dict[str, Pose] = {}

    def _load_pose(self, pose_name: str) -> Pose:
        if pose_name not in self._cache:
            self._cache[pose_name] = Pose.load(self._poses_dir / f"{pose_name}.yaml")
        return self._cache[pose_name]

    def move_to(self, arm: str, pose_name: str) -> None:
        _log.info("TeachReplay: move_to arm=%s pose=%s", arm, pose_name)
        pose = self._load_pose(pose_name)
        joints = pose.joints.get(arm)
        if joints is None:
            raise KeyError(f"Pose {pose_name!r} enthält keine Gelenkwinkel für Arm {arm!r}")
        self._robot.arm(arm).move_joints(joints)

    def follow(self, arm: str, trajectory: list[list[float]]) -> None:
        _log.info("TeachReplay: follow arm=%s waypoints=%d", arm, len(trajectory))
        for waypoint in trajectory:
            self._robot.arm(arm).move_joints(waypoint)
