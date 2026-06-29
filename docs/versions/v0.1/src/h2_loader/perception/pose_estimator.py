"""Posenschätzung (OpenCV heute, FoundationPose später) — Stub.

Implementiert ``PerceptionInterface``. Im ersten Ausbau nicht aktiv genutzt
(Teach-&-Replay arbeitet ohne Wahrnehmung); existiert als Andockpunkt.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import PerceptionInterface, Pose6D
from .camera import Camera

_log = get_logger(__name__)


class PoseEstimator(PerceptionInterface):
    """Schätzt Werkstückposen aus Kamerabildern (Stub).

    Args:
        camera: die Kamera, aus deren Bildern die Pose geschätzt wird.
    """

    def __init__(self, camera: Camera) -> None:
        self._camera = camera

    def locate_part(self, part_id: str) -> Pose6D | None:
        _log.info("PoseEstimator: locate_part %s (Stub -> None)", part_id)
        return None
