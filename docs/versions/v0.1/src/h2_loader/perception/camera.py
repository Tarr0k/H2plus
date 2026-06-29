"""Kamerazugriff (Kopf-/Handgelenkkamera) — Stub.

Liefert auf dem Zielsystem Frames (OpenCV) für die Posenschätzung. Hier nur
Gerüst, ohne Hardware-/Treiberanbindung.
"""

from __future__ import annotations

from ..util.logging import get_logger

_log = get_logger(__name__)


class Camera:
    """Kamera-Stub.

    Args:
        name: logischer Kameraname (z. B. "head", "wrist_left").
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def grab_frame(self) -> object:
        """Liefert ein Kamerabild (Stub: nicht implementiert)."""
        raise NotImplementedError(f"Camera[{self.name}].grab_frame: Stub")
