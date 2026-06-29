"""Roboter-Fassade: zwei Arme + gemeinsamer Treiber.

``Robot`` ist der Einstiegspunkt der HAL für höhere Schichten. Er hält beide
``Arm``-Instanzen und kapselt Verbindungsauf-/abbau über den Treiber. Skills
greifen auf ``robot.arm("left")`` und dessen Endeffektor zu — nie direkt auf
einen konkreten Treiber.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .arm import Arm
from .drivers.base import RobotDriverInterface

_log = get_logger(__name__)


class Robot:
    """Zweiarmiger H2 PLUS als Fassade über Treiber und Arme.

    Args:
        driver: gemeinsamer Lowlevel-Treiber für beide Arme.
        arms: Mapping Armseite -> ``Arm``-Instanz (üblich: "left", "right").
    """

    def __init__(self, driver: RobotDriverInterface, arms: dict[str, Arm]) -> None:
        self._driver = driver
        self._arms = arms

    def connect(self) -> None:
        _log.info("Robot: connect")
        self._driver.connect()

    def disconnect(self) -> None:
        _log.info("Robot: disconnect")
        self._driver.disconnect()

    def arm(self, side: str) -> Arm:
        """Liefert den Arm der angegebenen Seite ("left"/"right")."""
        if side not in self._arms:
            raise KeyError(f"Unbekannte Armseite: {side!r} (verfügbar: {sorted(self._arms)})")
        return self._arms[side]

    @property
    def sides(self) -> list[str]:
        return sorted(self._arms)
