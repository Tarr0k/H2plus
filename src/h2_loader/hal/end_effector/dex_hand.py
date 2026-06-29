"""Platzhalter für eine Mehrfingerhand (zukünftiger Endeffektor).

Im ersten Ausbau nicht verwendet (es kommt der Pneumatikgreifer zum Einsatz).
Existiert, um zu zeigen, dass das ``EndEffectorInterface`` einen Hand-Wechsel
ohne Änderung am Skill-Code trägt.
"""

from __future__ import annotations

from ...util.logging import get_logger
from .base import EndEffectorInterface

_log = get_logger(__name__)


class DexHand(EndEffectorInterface):
    """Mehrfingerhand (Stub) — Implementierung in einer späteren Ausbaustufe."""

    def grasp(self) -> None:
        raise NotImplementedError("DexHand.grasp: zukünftige Ausbaustufe")

    def release(self) -> None:
        raise NotImplementedError("DexHand.release: zukünftige Ausbaustufe")

    def is_holding(self) -> bool:
        raise NotImplementedError("DexHand.is_holding: zukünftige Ausbaustufe")
