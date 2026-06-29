"""Ventil-Aktor als Port (abstrakt) + zwei austauschbare Stub-Anbindungen.

Der pneumatische Greifer kennt nur "Ventil auf" / "Ventil zu". *Wie* das Ventil
physisch geschaltet wird, ist eine vertagte Entscheidung (siehe ADR-0002):

- ``PlcValveActuator``  — schaltet über die Maschinen-SPS (OPC-UA / digitaler Ausgang).
- ``H2IoValveActuator`` — schaltet über die bordeigene H2-IO (RS485/CAN).

Beide implementieren denselben ``ValveActuator``-Port und werden dem Greifer
injiziert. Die konkrete Wahl fällt später; die Architektur bleibt offen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...util.logging import get_logger

_log = get_logger(__name__)


class ValveActuator(ABC):
    """Port für einen 2/2-Wege-Pneumatik-Aktor (auf/zu)."""

    @abstractmethod
    def open(self) -> None:
        """Schaltet das Ventil auf (Druck auf Greiferzylinder)."""

    @abstractmethod
    def close(self) -> None:
        """Schaltet das Ventil zu (Greiferzylinder entlüftet/gegenrichtung)."""


class PlcValveActuator(ValveActuator):
    """Ventil über die Maschinen-SPS schalten (Stub).

    Args:
        plc: ein ``PlcInterface``, über das der Ventil-Ausgang gesetzt wird.
        signal: Name des SPS-Signals/Ausgangs für dieses Ventil.
    """

    def __init__(self, plc: object, signal: str) -> None:
        self._plc = plc
        self._signal = signal

    def open(self) -> None:
        _log.info("PlcValveActuator: open via SPS-Signal %s (Stub)", self._signal)
        # Zielsystem: self._plc.write_signal(self._signal, True)

    def close(self) -> None:
        _log.info("PlcValveActuator: close via SPS-Signal %s (Stub)", self._signal)
        # Zielsystem: self._plc.write_signal(self._signal, False)


class H2IoValveActuator(ValveActuator):
    """Ventil über die bordeigene H2-IO schalten (Stub, RS485/CAN).

    Args:
        channel: IO-Kanal/Adresse des Ventils auf dem H2-Bus.
    """

    def __init__(self, channel: int) -> None:
        self._channel = channel

    def open(self) -> None:
        _log.info("H2IoValveActuator: open auf Kanal %d (Stub)", self._channel)

    def close(self) -> None:
        _log.info("H2IoValveActuator: close auf Kanal %d (Stub)", self._channel)
