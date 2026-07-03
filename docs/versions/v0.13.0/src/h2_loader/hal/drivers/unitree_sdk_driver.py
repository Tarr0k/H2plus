"""Treiber für die echte H2-Hardware via ``unitree_sdk2_python``.

Bindet auf dem Zielsystem (Ubuntu 22.04, CycloneDDS 0.10.2) das
``unitree_sdk2_python``-SDK an. Der Import des SDK erfolgt bewusst lazy
(innerhalb der Methoden), damit dieses Modul auch auf Maschinen ohne SDK
(z. B. dieser Windows-Entwicklungsrechner) importierbar und testbar bleibt.

⚠️ HARDWARE-UNTESTED — SICHERHEIT VOR DEM ERSTEN REALLAUF LESEN:
    Dieser Treiber ist an den offiziellen ``unitree_sdk2py``-h2-Beispielen
    orientiert (siehe docs/sdk_reference.md), aber NOCH NIE gegen echte
    Hardware verifiziert. Vor dem ersten Reallauf jede Zeile gegen die
    aktuellen Beispiele im Ziel-SDK gegenprüfen (insbesondere Feldnamen von
    ``LowCmd_``/``LowState_`` und das arm_sdk-Gewichtungsschema).

    NUR mit aktivem **Debug-Modus** an der Fernbedienung betreiben
    (L2+R2 aktivieren, L2+A bestätigen, L2+B Notfall-Damping) — ohne
    Debug-Modus sendet das automatisch startende Motion-Control-Programm
    parallel eigene Befehle, was zu Befehlskonflikten (Zittern) führt.

    Voraussetzung: **H2 EDU** (Standard-H2 erlaubt keine Secondary
    Development / keinen SDK-Zugriff).

Reale API (Humanoid, siehe docs/sdk_reference.md):
  - ``ChannelFactoryInitialize(0, "enp3s0")`` (real) bzw. ``(1, "lo")`` (Sim).
  - Low-Level über die ``unitree_hg``-IDL: ``LowCmd_``/``LowState_`` (NICHT ``unitree_go``),
    Gelenkindizes via ``H2JointIndex`` (29 Achsen), je Gelenk kp/kd/q/dq/tau.
  - CRC (``unitree_sdk2py.utils.crc.CRC``) sichert jedes ``LowCmd_``-Paket ab.
  - Arm-only optional über ``arm_sdk`` (Gewichtungs-Member, steuert wie stark
    der Arm-Befehl gegenüber dem Onboard-Balance-Regler greift).
  - DDS-Topics: ``rt/lowcmd`` (schreiben), ``rt/lowstate`` (lesen).
"""

from __future__ import annotations

from ...util.logging import get_logger
from ..h2_joint_index import H2JointIndex
from .base import JointState, RobotDriverInterface

_log = get_logger(__name__)

# Konservative Regelparameter für send_joints — bewusst klein gewählt, um beim
# allerersten Rollout keine harten/schnellen Bewegungen auszulösen. Am
# Zielsystem anhand des realen Verhaltens hochsetzen (siehe Bring-up, Phase 3).
_KP_CONSERVATIVE = 20.0
_KD_CONSERVATIVE = 1.0

# arm_sdk-Gewichtungsschema laut h2_arm_sdk_dds_example: ein Gewichtswert (0..1)
# wird im q-Feld eines dafür vorgesehenen, nicht zum Arm gehörenden Motor-Slots
# abgelegt und steuert, wie stark der Arm-Befehl gegenüber dem Onboard-Balance-
# Regler greift. Index/Feldname sind NICHT durch dieses Repo verifiziert — vor
# dem ersten Reallauf gegen das aktuelle SDK-Beispiel prüfen.
_ARM_SDK_WEIGHT_INDEX = 29
_ARM_SDK_WEIGHT_VALUE = 1.0


class UnitreeSdkDriver(RobotDriverInterface):
    """Echte HW-Anbindung an den Unitree H2 (EDU) via ``unitree_sdk2py``.

    Siehe Modul-Docstring für die Sicherheitshinweise (Debug-Modus Pflicht).

    Args:
        network_interface: Ethernet-Interface für die DDS-Kommunikation
            (z. B. ``"enp3s0"``); ``None`` lässt ``ChannelFactoryInitialize``
            das Standard-Interface wählen.
        domain_id: DDS-Domain-ID (0 = real, 1 = Sim/Loopback laut SDK-Konvention).
        enable_commanding: Sicherheits-Sperre — solange ``False`` (Standard),
            wirft ``send_joints`` einen ``RuntimeError`` statt Gelenke zu
            bewegen. Nur nach expliziter Freigabe und im Debug-Modus aktivieren.
    """

    def __init__(
        self,
        network_interface: str | None = None,
        domain_id: int = 0,
        enable_commanding: bool = False,
    ) -> None:
        self._iface = network_interface
        self._domain_id = domain_id
        self._enable_commanding = enable_commanding
        self._connected = False
        self._state = JointState(positions={"left": [0.0] * 7, "right": [0.0] * 7})
        self._last_low_state: object | None = None
        self._subscriber: object | None = None
        self._publisher: object | None = None
        self._crc: object | None = None
        self._cmd_template: object | None = None

    def connect(self) -> None:
        """Baut die DDS-Verbindung auf: Subscriber auf ``rt/lowstate``, optional Publisher auf ``rt/lowcmd``.

        Raises:
            ImportError: wenn ``unitree_sdk2py`` auf diesem Rechner nicht installiert ist.
        """
        from unitree_sdk2py.core.channel import (  # noqa: PLC0415  # Lazy-Import bewusst
            ChannelFactoryInitialize,
            ChannelPublisher,
            ChannelSubscriber,
        )
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_  # noqa: PLC0415
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_  # noqa: PLC0415
        from unitree_sdk2py.utils.crc import CRC  # noqa: PLC0415

        _log.warning(
            "UnitreeSdkDriver.connect: Hardware-untested — entspricht den unitree_sdk2py "
            "h2-Beispielen, am ersten Reallauf verifizieren. NUR mit aktivem Debug-Modus an "
            "der Fernbedienung betreiben (L2+R2 aktivieren, L2+A bestaetigen, L2+B Not-Damping) "
            "— sonst Konflikt mit dem auto-startenden Motion-Control (Zittern)."
        )

        if self._iface:
            ChannelFactoryInitialize(self._domain_id, self._iface)
        else:
            ChannelFactoryInitialize(self._domain_id)

        self._subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self._subscriber.Init(self._on_low_state, 10)

        if self._enable_commanding:
            _log.warning(
                "UnitreeSdkDriver.connect: enable_commanding=True — send_joints() kann jetzt "
                "tatsaechlich Gelenke ansteuern. NUR im Debug-Modus verwenden."
            )
            publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
            publisher.Init()
            self._publisher = publisher
            self._crc = CRC()
            self._cmd_template = unitree_hg_msg_dds__LowCmd_()

        self._connected = True
        _log.info(
            "UnitreeSdkDriver: verbunden (domain_id=%d, iface=%s, enable_commanding=%s)",
            self._domain_id, self._iface, self._enable_commanding,
        )

    def _on_low_state(self, msg: object) -> None:
        """DDS-Callback: puffert den zuletzt empfangenen ``LowState_`` (wird von ``read_state`` gelesen)."""
        self._last_low_state = msg

    def disconnect(self) -> None:
        self._connected = False
        self._subscriber = None
        self._publisher = None
        _log.info("UnitreeSdkDriver: getrennt")

    def send_joints(self, arm: str, positions: list[float]) -> None:
        """Sendet Soll-Gelenkwinkel [rad] für den angegebenen Arm — sicherheitsgesperrt.

        Args:
            arm: "left" oder "right".
            positions: 7 Soll-Gelenkwinkel [rad] in ``H2JointIndex``-Reihenfolge.

        Raises:
            RuntimeError: wenn ``enable_commanding=False`` (Sicherheitssperre).
            ValueError: bei falscher Anzahl Gelenkwinkel.
        """
        if not self._enable_commanding:
            _log.error(
                "UnitreeSdkDriver.send_joints: enable_commanding=False — Sicherheitssperre aktiv, "
                "kein Befehl gesendet (arm=%s)", arm,
            )
            raise RuntimeError(
                "UnitreeSdkDriver.send_joints: gesperrt (enable_commanding=False). "
                "Nur mit expliziter Freigabe und aktivem Debug-Modus verwenden."
            )

        indices = H2JointIndex.LEFT_ARM if arm == "left" else H2JointIndex.RIGHT_ARM
        if len(positions) != len(indices):
            raise ValueError(
                f"send_joints: erwarte {len(indices)} Gelenkwinkel für Arm {arm!r}, erhielt {len(positions)}"
            )
        if self._publisher is None or self._crc is None or self._cmd_template is None:
            raise RuntimeError("UnitreeSdkDriver.send_joints: connect() nicht (oder ohne enable_commanding) aufgerufen")

        # SICHERHEIT: konservative kp/kd, dq=0, tau=0 — reine Positionsvorgabe.
        cmd = self._cmd_template
        for idx, q in zip(indices, positions):
            motor = cmd.motor_cmd[idx]
            motor.q = q
            motor.dq = 0.0
            motor.tau = 0.0
            motor.kp = _KP_CONSERVATIVE
            motor.kd = _KD_CONSERVATIVE

        try:
            cmd.motor_cmd[_ARM_SDK_WEIGHT_INDEX].q = _ARM_SDK_WEIGHT_VALUE
        except (IndexError, AttributeError) as exc:  # pragma: no cover — nur auf Zielsystem relevant
            _log.warning(
                "UnitreeSdkDriver.send_joints: arm_sdk-Gewicht konnte nicht gesetzt werden (%s) — "
                "gegen aktuelles SDK-Beispiel pruefen", exc,
            )

        cmd.crc = self._crc.Crc(cmd)
        self._publisher.Write(cmd)
        _log.info(
            "UnitreeSdkDriver.send_joints: arm=%s positions=%s gesendet (kp=%.1f kd=%.1f)",
            arm, positions, _KP_CONSERVATIVE, _KD_CONSERVATIVE,
        )

    def read_state(self) -> JointState:
        """Liest die Ist-Gelenkwinkel beider Arme aus dem zuletzt empfangenen ``LowState_``."""
        if self._last_low_state is None:
            _log.warning("UnitreeSdkDriver.read_state: noch kein LowState_ empfangen — liefere Nullen")
            return self._state
        motor_state = self._last_low_state.motor_state  # type: ignore[attr-defined]
        left = [motor_state[i].q for i in H2JointIndex.LEFT_ARM]
        right = [motor_state[i].q for i in H2JointIndex.RIGHT_ARM]
        self._state = JointState(positions={"left": left, "right": right})
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._connected
