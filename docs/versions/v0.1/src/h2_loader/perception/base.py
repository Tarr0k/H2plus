"""Interface für die Wahrnehmung.

Im ersten Ausbau arbeitet der Lader mit fest angelernten Posen — Wahrnehmung ist
optional. Das Interface existiert, damit später (z. B. FoundationPose / Open3D)
ein 6D-Lokalisieren von Werkstücken ergänzt werden kann, ohne Skills umzubauen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Pose6D:
    """6D-Pose eines Objekts im Roboter-Koordinatensystem.

    Translation [m] und Rotation als Quaternion (x, y, z, w).
    """

    x: float
    y: float
    z: float
    qx: float
    qy: float
    qz: float
    qw: float


class PerceptionInterface(ABC):
    """Abstrakte Wahrnehmung: ein Werkstück lokalisieren."""

    @abstractmethod
    def locate_part(self, part_id: str) -> Pose6D | None:
        """Liefert die 6D-Pose des Werkstücks oder None, wenn nicht gefunden."""
