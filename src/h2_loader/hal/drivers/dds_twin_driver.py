"""DDS-Twin-Treiber: fährt den H2 im unitree_mujoco-Twin über DDS.

Im Unterschied zu ``UnitreeSdkDriver`` (echte HW, arm-only via arm_sdk — die Beine
macht dort der Onboard-Balance-Regler) steuert dieser Treiber im TWIN den
GANZEN Körper per Lowlevel-``LowCmd`` (unitree_hg, 31 Motoren): Beine/Taille/Kopf
werden auf einer Stehpose gehalten, die Arme folgen ``send_joints``. So kann die
komplette ``h2_loader``-App (Orchestrator + Lade-Skills) gegen den Physik-Twin
laufen, ohne echte Hardware.

Voraussetzung: der unitree_mujoco-Twin läuft (DDS Domain 1, iface ``lo``; z. B.
``training/deploy/dds_twin_headless.py``) und die Bridge ist H2-tauglich gepatcht
(``scripts/patch_unitree_mujoco_h2.sh``).

WICHTIG (ADR-0008): Ein reiner Positions-Halteregler stabilisiert den H2 NICHT
dauerhaft (instabiles Gleichgewicht — kippt nach einigen Sekunden). Dieser Treiber
belegt den Kommandopfad (App → Twin) und dient für Ablauf-/Handshake-Tests; für
stabiles Stehen/Gehen liefert die RL-Policy die Beinbefehle (künftig als LowCmd-Quelle).

Der SDK-Import ist lazy (in ``connect``), damit das Modul ohne ``unitree_sdk2py``
importierbar/testbar bleibt (z. B. auf dem Windows-Entwicklungsrechner).
"""

from __future__ import annotations

import threading
import time

from ...util.logging import get_logger
from .base import JointState, RobotDriverInterface

_log = get_logger(__name__)

_NUM_MOTOR = 31
# Aktuator-Index-Bereiche (verifiziert): Beine 0-11, Taille 12-14, linker Arm
# 15-21, rechter Arm 22-28, Kopf 29-30.
_ARM_IDX = {"left": list(range(15, 22)), "right": list(range(22, 29))}

# Stehpose je Aktuator (H2-Knöchelreihenfolge roll VOR pitch), leichte Kniebeuge.
_LEG = [-0.3, 0.0, 0.0, 0.6, 0.0, -0.3]
_HOME = _LEG + _LEG + [0.0] * 3 + [0.0] * 14 + [0.0] * 2  # 31

_KP_LEG = [150.0, 150.0, 150.0, 200.0, 80.0, 80.0]
_KD_LEG = [4.0, 4.0, 4.0, 5.0, 4.0, 4.0]
_KP = _KP_LEG + _KP_LEG + [150.0] * 3 + [40.0] * 14 + [10.0] * 2
_KD = _KD_LEG + _KD_LEG + [4.0] * 3 + [2.0] * 14 + [1.0] * 2


class DdsTwinDriver(RobotDriverInterface):
    """Ganzkörper-DDS-Treiber für den H2 im unitree_mujoco-Twin.

    Args:
        network_interface: DDS-Interface (Twin: ``"lo"``).
        domain_id: DDS-Domain (Twin-Konvention: 1).
        publish_hz: Sendefrequenz des Halte-/Arm-Befehls [Hz].
    """

    def __init__(self, network_interface: str = "lo", domain_id: int = 1, publish_hz: float = 200.0) -> None:
        self._iface = network_interface
        self._domain_id = domain_id
        self._period = 1.0 / publish_hz
        self._connected = False
        self._lock = threading.Lock()
        self._targets = list(_HOME)          # aktuelle Soll-Gelenkwinkel (31)
        self._last_state: JointState = JointState()
        self._pub = None
        self._crc = None
        self._cmd = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def connect(self) -> None:
        """Initialisiert DDS (rt/lowcmd + rt/lowstate) und startet den Sende-Thread."""
        from unitree_sdk2py.core.channel import (  # noqa: PLC0415
            ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber,
        )
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_  # noqa: PLC0415
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_  # noqa: PLC0415
        from unitree_sdk2py.utils.crc import CRC  # noqa: PLC0415

        ChannelFactoryInitialize(self._domain_id, self._iface)
        self._pub = ChannelPublisher("rt/lowcmd", LowCmd_)
        self._pub.Init()
        sub = ChannelSubscriber("rt/lowstate", LowState_)
        sub.Init(self._on_low_state, 10)
        self._crc = CRC()
        self._cmd = unitree_hg_msg_dds__LowCmd_()
        for i in range(_NUM_MOTOR):
            self._cmd.motor_cmd[i].mode = 1
            self._cmd.motor_cmd[i].kp = _KP[i]
            self._cmd.motor_cmd[i].kd = _KD[i]
            self._cmd.motor_cmd[i].dq = 0.0
            self._cmd.motor_cmd[i].tau = 0.0

        self._connected = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._publish_loop, name="dds_twin_pub", daemon=True)
        self._thread.start()
        _log.info("DdsTwinDriver: verbunden (domain=%d, iface=%s) — Ganzkörper-Halteregler aktiv",
                  self._domain_id, self._iface)

    def _on_low_state(self, msg: object) -> None:
        """DDS-Callback: puffert Arm-Gelenkwinkel aus ``LowState`` in ``read_state``-Form."""
        try:
            ms = msg.motor_state  # type: ignore[attr-defined]
            pos = {side: [float(ms[i].q) for i in idx] for side, idx in _ARM_IDX.items()}
            self._last_state = JointState(positions=pos, timestamp=time.time())
        except Exception as exc:  # LowState-Layout defensiv behandeln
            _log.debug("DdsTwinDriver: LowState-Parse fehlgeschlagen: %s", exc)

    def _publish_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                for i in range(_NUM_MOTOR):
                    self._cmd.motor_cmd[i].q = self._targets[i]
                self._cmd.crc = self._crc.Crc(self._cmd)
            self._pub.Write(self._cmd)
            time.sleep(self._period)

    def disconnect(self) -> None:
        """Stoppt den Sende-Thread und markiert die Verbindung als getrennt."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._connected = False
        _log.info("DdsTwinDriver: getrennt")

    def send_joints(self, arm: str, positions: list[float]) -> None:
        """Setzt die 7 Soll-Gelenkwinkel des angegebenen Arms (Beine/Taille bleiben Halte-Pose)."""
        if arm not in _ARM_IDX:
            raise ValueError(f"send_joints: Arm {arm!r} unbekannt (erwartet 'left'/'right')")
        idx = _ARM_IDX[arm]
        if len(positions) != len(idx):
            raise ValueError(f"send_joints: erwarte {len(idx)} Winkel für Arm {arm!r}, erhielt {len(positions)}")
        if not self._connected:
            raise RuntimeError("DdsTwinDriver.send_joints: connect() fehlt")
        with self._lock:
            for k, i in enumerate(idx):
                self._targets[i] = float(positions[k])

    def read_state(self) -> JointState:
        """Letzter über DDS empfangener Arm-Gelenkzustand (aus ``rt/lowstate``)."""
        return self._last_state

    @property
    def is_connected(self) -> bool:
        return self._connected
