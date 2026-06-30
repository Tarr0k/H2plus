"""Arm-Abstraktion: ein 7-DoF-Arm samt zugeordnetem Endeffektor.

Ein ``Arm`` bündelt low-level Gelenkansteuerung (über den injizierten
``RobotDriverInterface``) und den Endeffektor dieses Arms. Der H2 PLUS hat zwei
Arme ("left"/"right"); jeder bekommt eine eigene ``Arm``-Instanz.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .drivers.base import RobotDriverInterface
from .end_effector.base import EndEffectorInterface

_log = get_logger(__name__)


class Arm:
    """Ein 7-DoF-Arm mit Endeffektor.

    Args:
        side: "left" oder "right".
        driver: gemeinsamer Lowlevel-Treiber (Sim oder reale HW).
        end_effector: der diesem Arm zugeordnete Endeffektor.
    """

    DOF = 7

    def __init__(self, side: str, driver: RobotDriverInterface, end_effector: EndEffectorInterface) -> None:
        self.side = side
        self._driver = driver
        self.end_effector = end_effector

    def move_joints(self, positions: list[float]) -> None:
        """Fährt die 7 Gelenke auf die angegebenen Sollwinkel [rad]."""
        if len(positions) != self.DOF:
            raise ValueError(f"Arm {self.side}: erwarte {self.DOF} Gelenkwinkel, erhielt {len(positions)}")
        _log.info("Arm[%s]: move_joints %s", self.side, positions)
        self._driver.send_joints(self.side, positions)

    def set_end_effector(self, ee: EndEffectorInterface) -> None:
        """Ersetzt den Endeffektor dieses Arms (Tool-Changer-Schnittstelle).

        Wird vom ``ToolChanger`` aufgerufen, um das montierte Werkzeug zu
        wechseln. Nach dem Aufruf liefert ``end_effector`` die neue Instanz.

        Args:
            ee: Der neue Endeffektor.
        """
        _log.info("Arm[%s]: set_end_effector -> %s", self.side, type(ee).__name__)
        self.end_effector = ee

    def current_joints(self) -> list[float]:
        """Liest die aktuellen Gelenkwinkel dieses Arms."""
        return self._driver.read_state().positions.get(self.side, [0.0] * self.DOF)
