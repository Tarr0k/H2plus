"""Treiber für die echte H2-Hardware via ``unitree_sdk2_python`` (Stub).

Auf dem Zielsystem (Ubuntu 22.04, CycloneDDS 0.10.2) bindet dieser Treiber das
``unitree_sdk2_python`` an. Hier nur Gerüst: der Import des SDK erfolgt bewusst
lazy in ``connect()``, damit das Paket auch auf Maschinen ohne SDK importierbar
und testbar bleibt.

Reale API (Humanoid, siehe docs/sdk_reference.md):
  - ``ChannelFactoryInitialize(0, "enp3s0")`` (real) bzw. ``(1, "lo")`` (Sim).
  - Low-Level über die ``unitree_hg``-IDL: ``LowCmd_``/``LowState_`` (NICHT ``unitree_go``),
    Gelenkindizes via ``H2JointIndex`` (29 Achsen), je Gelenk kp/kd/q/dq/tau.
  - CRC (``unitree_sdk2py.utils.crc.CRC``) + Hochfrequenz-Loop (``RecurrentThread``).
  - FSM-Hochfahrsequenz ``Start`` → ``StandUp`` vor Bewegung.
  - Arm-only optional über ``arm_sdk`` (Gewichtungs-Member).
"""

from __future__ import annotations

from ...util.logging import get_logger
from .base import JointState, RobotDriverInterface

_log = get_logger(__name__)


class UnitreeSdkDriver(RobotDriverInterface):
    """Echte HW-Anbindung (Stub) — Implementierung auf dem Zielsystem."""

    def __init__(self, network_interface: str | None = None) -> None:
        self._iface = network_interface
        self._connected = False
        self._state = JointState(positions={"left": [0.0] * 7, "right": [0.0] * 7})

    def connect(self) -> None:
        # Auf dem Zielsystem hier: ChannelFactoryInitialize(0, self._iface) etc.
        _log.warning("UnitreeSdkDriver.connect: Stub — SDK-Anbindung folgt auf dem Zielsystem")
        raise NotImplementedError("unitree_sdk2_python-Anbindung wird auf dem Ubuntu-Zielsystem implementiert")

    def disconnect(self) -> None:
        self._connected = False

    def send_joints(self, arm: str, positions: list[float]) -> None:
        raise NotImplementedError("send_joints: Stub")

    def read_state(self) -> JointState:
        raise NotImplementedError("read_state: Stub")

    @property
    def is_connected(self) -> bool:
        return self._connected
