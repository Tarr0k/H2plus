"""Interface zur Maschinen-SPS.

Skills lesen/schreiben Signale ausschließlich über ``PlcInterface`` und die
``Signal``-Enum. Ob dahinter OPC-UA, Modbus oder ein Mock steckt, ist für den
Skill unsichtbar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .signals import Signal


class PlcInterface(ABC):
    """Abstrakte SPS: einzelnes Signal lesen/schreiben, auf Zustand warten."""

    @abstractmethod
    def read_signal(self, signal: Signal) -> bool:
        """Liest den aktuellen Wert eines (booleschen) Signals."""

    @abstractmethod
    def write_signal(self, signal: Signal, value: bool) -> None:
        """Setzt den Wert eines (booleschen) Signals."""

    @abstractmethod
    def wait_for(self, signal: Signal, value: bool = True, timeout_s: float | None = None) -> bool:
        """Wartet, bis ``signal`` den Wert ``value`` annimmt.

        Returns:
            True, wenn der Zustand erreicht wurde; False bei Timeout.
        """
