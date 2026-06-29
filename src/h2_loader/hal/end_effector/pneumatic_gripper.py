"""Pneumatischer 1-Zylinder-Backengreifer.

Der schlichteste vorgesehene Endeffektor: ein Zylinder, auf/zu. Greifen und
Loslassen werden auf ``ValveActuator.open()``/``close()`` abgebildet. Der
Aktor wird injiziert (Dependency Injection) — der Greifer weiß nicht, ob das
Ventil an der SPS oder an der H2-IO hängt.
"""

from __future__ import annotations

from ...util.logging import get_logger
from .base import EndEffectorInterface
from .valve_actuator import ValveActuator

_log = get_logger(__name__)


class PneumaticGripper(EndEffectorInterface):
    """1-Zylinder-Backengreifer über einen injizierten ``ValveActuator``.

    Args:
        valve: der Ventil-Aktor, der den Greiferzylinder schaltet.
        normally_open: True, wenn "Ventil auf" = Greifer öffnet. Default False
            (Ventil auf = greifen), je nach Verschlauchung per Config setzbar.
    """

    def __init__(self, valve: ValveActuator, normally_open: bool = False) -> None:
        self._valve = valve
        self._normally_open = normally_open
        self._holding = False

    def grasp(self) -> None:
        _log.info("PneumaticGripper: grasp")
        self._valve.close() if self._normally_open else self._valve.open()
        self._holding = True

    def release(self) -> None:
        _log.info("PneumaticGripper: release")
        self._valve.open() if self._normally_open else self._valve.close()
        self._holding = False

    def is_holding(self) -> bool:
        # Ohne Greifkraft-/Positionssensorik nur der angenommene Zustand.
        return self._holding
