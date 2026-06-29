"""MuJoCo-Simulationstreiber (Stub).

Implementiert ``RobotDriverInterface`` gegen ``unitree_mujoco``. Da MuJoCo-Sim
und reale HW dieselbe DDS-Schnittstelle teilen, ist der Wechsel zur echten HW
ein Konfig-Einzeiler (``driver: sim`` -> ``driver: sdk``).

Stub-Stand: hält den letzten gesendeten Gelenkzustand im Speicher und loggt die
Aufrufe. Keine echte Physik/DDS-Anbindung — die erfolgt auf dem Zielsystem.
"""

from __future__ import annotations

from ...util.logging import get_logger
from .base import JointState, RobotDriverInterface

_log = get_logger(__name__)


class MujocoSimDriver(RobotDriverInterface):
    """In-Memory-Simulationstreiber für Tests ohne Hardware."""

    def __init__(self) -> None:
        self._connected = False
        self._state = JointState(positions={"left": [0.0] * 7, "right": [0.0] * 7})

    def connect(self) -> None:
        _log.info("MuJoCo-Sim: connect (Stub)")
        self._connected = True

    def disconnect(self) -> None:
        _log.info("MuJoCo-Sim: disconnect (Stub)")
        self._connected = False

    def send_joints(self, arm: str, positions: list[float]) -> None:
        _log.info("MuJoCo-Sim: send_joints arm=%s positions=%s", arm, positions)
        self._state.positions[arm] = list(positions)

    def read_state(self) -> JointState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._connected
