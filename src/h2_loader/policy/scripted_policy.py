"""Teach-&-Replay-Backend als Policy (deterministisch).

``ScriptedPolicy`` implementiert ``PolicyInterface`` durch Abfahren
angelernter Posen — der heutige Teach-in-Pfad (v0.6.0) als Policy-Backend.
Es lädt bei ``predict()`` die Pose, deren Name in ``obs.goal`` steht, aus
``poses_dir`` und liefert die Gelenkwinkel des gewählten Arms als ``Action``.

Dieses Backend ist deterministisch und dient dauerhaft als Fallback, falls
``GrootPolicy`` ausfällt (siehe ADR-0007, Stufe 3).
"""

from __future__ import annotations

from pathlib import Path

from ..util.config import Pose
from ..util.logging import get_logger
from .base import Action, Observation, PolicyInterface

_log = get_logger(__name__)


class ScriptedPolicy(PolicyInterface):
    """Teach-in-Posen als Policy-Backend (deterministisch).

    Lädt angelernte Posen aus ``poses_dir`` und liefert deren Gelenkwinkel
    direkt als ``Action``. Kein Bahnplaner, kein Modell — rein deterministisch.

    Args:
        poses_dir: Verzeichnis mit ``<pose_name>.yaml``-Dateien.
        arm:       Armseite, für die Gelenkwinkel geliefert werden ("right").
    """

    name = "scripted"

    def __init__(self, poses_dir: Path | str, arm: str = "right") -> None:
        self._poses_dir = Path(poses_dir)
        self._arm = arm
        self._cache: dict[str, Pose] = {}

    def _load_pose(self, pose_name: str) -> Pose:
        """Lädt eine Pose per Namen (intern gecacht)."""
        if pose_name not in self._cache:
            pose_path = self._poses_dir / f"{pose_name}.yaml"
            if not pose_path.is_file():
                raise FileNotFoundError(
                    f"ScriptedPolicy: Pose-Datei nicht gefunden: {pose_path}"
                )
            self._cache[pose_name] = Pose.load(pose_path)
        return self._cache[pose_name]

    def predict(self, obs: Observation) -> Action:
        """Liefert die Gelenkwinkel der benannten Pose als Action.

        Args:
            obs: Beobachtung; ``obs.goal`` muss den Posen-Namen enthalten.

        Returns:
            ``Action`` mit den 7 Gelenkwinkeln der Pose für ``self._arm``.

        Raises:
            ValueError: wenn ``obs.goal`` nicht gesetzt ist.
            FileNotFoundError: wenn die Pose-Datei nicht existiert.
            KeyError: wenn die Pose keine Gelenkwinkel für den gewählten Arm hat.
        """
        if not obs.goal:
            raise ValueError(
                "ScriptedPolicy.predict: obs.goal muss einen Posen-Namen enthalten"
            )
        _log.info("ScriptedPolicy: predict goal=%s arm=%s", obs.goal, self._arm)
        pose = self._load_pose(obs.goal)
        joints = pose.joints.get(self._arm)
        if joints is None:
            raise KeyError(
                f"ScriptedPolicy: Pose {obs.goal!r} enthält keine Gelenkwinkel "
                f"für Arm {self._arm!r}"
            )
        return Action(arm=self._arm, joint_targets=joints)
