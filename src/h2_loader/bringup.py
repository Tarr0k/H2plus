"""Gestufter, sicherheits-gegateter Hardware-Bring-up für den Unitree H2 (EDU).

Führt den ersten Reallauf in klar getrennten, einzeln überspringbaren Phasen
durch, damit am ersten Tag am Roboter schnell — aber sicher — vorangekommen
wird. Jede Phase loggt ihr Ergebnis und liefert ``bool`` zurück; ``run()``
bricht bei der ersten fehlgeschlagenen Phase ab.

⚠️ HARDWARE-UNTESTED — entspricht den ``unitree_sdk2py``-h2-Beispielen laut
docs/sdk_reference.md, aber noch nie gegen echte Hardware verifiziert. Vor
dem ersten Reallauf jede Phase gegen das aktuelle SDK gegenprüfen.

NUR mit aktivem **Debug-Modus** an der Fernbedienung betreiben (L2+R2
aktivieren, L2+A bestätigen, L2+B Notfall-Damping) — sonst kollidiert das
automatisch startende Motion-Control-Programm mit den SDK-Befehlen (Zittern).

Phasen:
    0 — Netzwerk-Check + Debug-Modus-Erinnerung (Ping Mainboard).
    1 — DDS-Verbindung: Treiber verbinden, Ist-Zustand beider Arme lesen.
    2 — Locomotion-Bring-up: FSM hochfahren (Damp → Start → StandUp).
    3 — Arme in Home-Pose fahren (nur mit Sicherheitsfreigabe + ``enable_commanding``).
    4 — SPS-Handshake: OPC-UA-Verbindung + Heartbeat-Round-Trip.

Alle Komponenten werden injiziert (``RobotDriverInterface``, ``VelocitySink``,
``H2HandshakeClient``, ``SafetyGate``), damit ``BringupSequencer`` mit Mocks
testbar bleibt, ohne SDK oder Roboter zu benötigen.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
from typing import TYPE_CHECKING

from .core.safety import SafetyGate
from .hal.drivers.unitree_sdk_driver import UnitreeSdkDriver
from .hal.locomotion.velocity_sink import LocoClientVelocitySink
from .plc.asyncua_transport import AsyncuaTransport
from .plc.handshake import H2HandshakeClient
from .util.logging import get_logger

if TYPE_CHECKING:
    from .hal.drivers.base import RobotDriverInterface
    from .hal.locomotion.velocity_sink import VelocitySink

_log = get_logger(__name__)

_DEFAULT_MAINBOARD_IP = "192.168.123.161"
_DEFAULT_HOME_POSE: dict[str, list[float]] = {"left": [0.0] * 7, "right": [0.0] * 7}


class BringupSequencer:
    """Orchestriert die Bring-up-Phasen 0–4 mit injizierten Komponenten.

    Args:
        driver:            Lowlevel-Treiber (Phase 1/3), z. B. ``UnitreeSdkDriver``.
        sink:               Velocity-Sink (Phase 2), z. B. ``LocoClientVelocitySink``.
        handshake:          SPS-Handshake-Client (Phase 4).
        safety:             Sicherheits-Gate/-Supervisor (Phase 3 prüft ``is_clear()``).
        network_interface:  Ethernet-Interface, nur für Phase 0 (Ping-Kontext, informativ).
        mainboard_ip:       IP des H2-Mainboards für den Ping in Phase 0.
        home_pose:          Home-Gelenkwinkel je Arm für Phase 3.
    """

    def __init__(
        self,
        driver: RobotDriverInterface | None = None,
        sink: VelocitySink | None = None,
        handshake: H2HandshakeClient | None = None,
        safety: SafetyGate | None = None,
        network_interface: str | None = None,
        mainboard_ip: str = _DEFAULT_MAINBOARD_IP,
        home_pose: dict[str, list[float]] | None = None,
    ) -> None:
        self._driver = driver
        self._sink = sink
        self._handshake = handshake
        self._safety = safety
        self._iface = network_interface
        self._mainboard_ip = mainboard_ip
        self._home_pose = home_pose if home_pose is not None else dict(_DEFAULT_HOME_POSE)

    # ------------------------------------------------------------------
    # Hilfsmittel
    # ------------------------------------------------------------------

    @staticmethod
    def _confirm(prompt: str) -> bool:
        """Fragt an der Konsole nach Bestätigung; nur bei Sicherheitsrelevanz genutzt."""
        answer = input(f"{prompt} [j/N]: ").strip().lower()
        return answer in ("j", "ja", "y", "yes")

    # ------------------------------------------------------------------
    # Phasen
    # ------------------------------------------------------------------

    def phase0_check(self, iface: str | None, mainboard_ip: str = _DEFAULT_MAINBOARD_IP) -> bool:
        """Phase 0: Netzwerk-Erreichbarkeit des Mainboards + Debug-Modus-Erinnerung.

        Args:
            iface:        Ethernet-Interface (nur zur Information geloggt).
            mainboard_ip: IP-Adresse des H2-Mainboards.

        Returns:
            True, wenn der Ping erfolgreich war.
        """
        _log.info("Bringup Phase 0: Netzwerk-Check (iface=%s, mainboard=%s)", iface, mainboard_ip)
        _log.warning(
            "Sicherstellen: Debug-Modus an der Fernbedienung aktiv (L2+R2 aktivieren, "
            "L2+A bestaetigen, L2+B Not-Damping) — sonst Konflikt mit dem auto-startenden "
            "Motion-Control (Zittern)."
        )
        count_flag = "-n" if platform.system() == "Windows" else "-c"
        cmd = ["ping", count_flag, "1", mainboard_ip]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            _log.error("Phase 0 fehlgeschlagen: Ping konnte nicht ausgefuehrt werden (%s)", exc)
            return False
        ok = result.returncode == 0
        if ok:
            _log.info("Phase 0: Mainboard %s erreichbar", mainboard_ip)
        else:
            _log.error("Phase 0 fehlgeschlagen: Mainboard %s nicht erreichbar (returncode=%d)", mainboard_ip, result.returncode)
        return ok

    def phase1_dds(self, driver: RobotDriverInterface) -> bool:
        """Phase 1: Treiber verbinden und Ist-Zustand beider Arme lesen.

        Args:
            driver: Lowlevel-Treiber (``UnitreeSdkDriver`` oder Mock).

        Returns:
            True, wenn beide Arme je 7 Gelenkwerte liefern.
        """
        _log.info("Bringup Phase 1: DDS-Verbindung + State-Lesbarkeit")
        try:
            driver.connect()
            state = driver.read_state()
        except Exception as exc:  # noqa: BLE001 — Bring-up soll robust abbrechen, nicht crashen
            _log.error("Phase 1 fehlgeschlagen: %s", exc)
            return False
        left = state.positions.get("left", [])
        right = state.positions.get("right", [])
        if len(left) != 7 or len(right) != 7:
            _log.error(
                "Phase 1 fehlgeschlagen: erwarte 7+7 Gelenkwerte, erhielt links=%d rechts=%d",
                len(left), len(right),
            )
            return False
        _log.info("Phase 1: DDS OK — links=%s rechts=%s", left, right)
        return True

    def phase2_loco(self, sink: VelocitySink, assume_yes: bool = False) -> bool:
        """Phase 2: Locomotion-Bring-up (Damp → Start → StandUp).

        ⚠️ SICHERHEIT: Der Roboter steht auf — nur mit freiem Umfeld bestätigen.

        Args:
            sink:        Velocity-Sink (``LocoClientVelocitySink`` oder Mock).
            assume_yes:  Überspringt die Sicherheitsabfrage, wenn True.

        Returns:
            True bei erfolgreichem Bring-up.
        """
        if not assume_yes and not self._confirm(
            "Phase 2 faehrt den Roboter hoch (Damp -> Start -> StandUp). Fortfahren?"
        ):
            _log.warning("Phase 2 abgebrochen: keine Bestaetigung")
            return False
        _log.info("Bringup Phase 2: Locomotion-Bring-up")
        try:
            sink.connect()
            sink.bring_up()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            _log.error("Phase 2 fehlgeschlagen: %s", exc)
            return False
        _log.info("Phase 2: Locomotion OK")
        return True

    def phase3_arm_home(
        self,
        driver: RobotDriverInterface,
        home_pose: dict[str, list[float]],
        safety: SafetyGate,
        assume_yes: bool = False,
    ) -> bool:
        """Phase 3: Beide Arme langsam in die Home-Pose fahren.

        ⚠️ SICHERHEIT: Erfordert eine gültige Sicherheitsfreigabe (``safety.is_clear()``)
        und aktives ``enable_commanding`` am Treiber — sonst wirft ``send_joints``
        einen ``RuntimeError`` (siehe ``UnitreeSdkDriver``).

        Args:
            driver:      Lowlevel-Treiber mit freigeschaltetem Kommandieren.
            home_pose:   Mapping Armseite -> 7 Soll-Gelenkwinkel [rad].
            safety:      Sicherheits-Gate/-Supervisor.
            assume_yes:  Überspringt die Sicherheitsabfrage, wenn True.

        Returns:
            True, wenn beide Arme erfolgreich kommandiert wurden.
        """
        if not safety.is_clear():
            _log.error("Phase 3 verweigert: keine Sicherheitsfreigabe (safety.is_clear() == False)")
            return False
        if not assume_yes and not self._confirm(
            "Phase 3 faehrt beide Arme langsam in die Home-Pose. Fortfahren?"
        ):
            _log.warning("Phase 3 abgebrochen: keine Bestaetigung")
            return False
        _log.info("Bringup Phase 3: Arme in Home-Pose")
        try:
            for side in ("left", "right"):
                positions = home_pose.get(side)
                if positions is None:
                    _log.error("Phase 3 fehlgeschlagen: home_pose enthaelt keinen Eintrag fuer Arm '%s'", side)
                    return False
                driver.send_joints(side, positions)
        except Exception as exc:  # noqa: BLE001
            _log.error("Phase 3 fehlgeschlagen: %s", exc)
            return False
        _log.info("Phase 3: beide Arme in Home-Pose kommandiert")
        return True

    def phase4_plc(self, handshake: H2HandshakeClient) -> bool:
        """Phase 4: SPS-Handshake — Verbindung + Heartbeat-Round-Trip.

        Args:
            handshake: ``H2HandshakeClient`` (mit ``AsyncuaTransport`` verdrahtet).

        Returns:
            True, wenn connect/tick/read ohne Fehler durchlaufen.
        """
        _log.info("Bringup Phase 4: SPS-Handshake (OPC-UA)")
        try:
            handshake.connect()
            handshake.tick_heartbeat()
            value = handshake.read("control", "robotHeartbeat")
        except Exception as exc:  # noqa: BLE001
            _log.error("Phase 4 fehlgeschlagen: %s", exc)
            return False
        _log.info("Phase 4: SPS-Handshake OK (robotHeartbeat=%r)", value)
        return True

    # ------------------------------------------------------------------
    # Ablaufsteuerung
    # ------------------------------------------------------------------

    def run(self, phases: list[int], assume_yes: bool = False) -> bool:
        """Führt die angegebenen Phasen der Reihe nach aus; bricht bei Fehler ab.

        Args:
            phases:     Phasennummern (0–4) in Ausführungsreihenfolge.
            assume_yes: Überspringt Sicherheitsabfragen in Phase 2/3.

        Returns:
            True, wenn alle Phasen erfolgreich waren.
        """
        for phase in phases:
            if phase == 0:
                ok = self.phase0_check(self._iface, self._mainboard_ip)
            elif phase == 1:
                ok = self.phase1_dds(self._driver)  # type: ignore[arg-type]
            elif phase == 2:
                ok = self.phase2_loco(self._sink, assume_yes=assume_yes)  # type: ignore[arg-type]
            elif phase == 3:
                ok = self.phase3_arm_home(self._driver, self._home_pose, self._safety, assume_yes=assume_yes)  # type: ignore[arg-type]
            elif phase == 4:
                ok = self.phase4_plc(self._handshake)  # type: ignore[arg-type]
            else:
                raise ValueError(f"Unbekannte Bringup-Phase: {phase} (erwartet 0-4)")

            if not ok:
                _log.error("BringupSequencer: Phase %d fehlgeschlagen — Ablauf abgebrochen", phase)
                return False

        _log.info("BringupSequencer: alle angeforderten Phasen erfolgreich: %s", phases)
        return True


def main(argv: list[str] | None = None) -> int:
    """CLI-Einstiegspunkt: baut reale Komponenten und führt die gewünschten Phasen aus."""
    parser = argparse.ArgumentParser(prog="h2-bringup", description="H2 (EDU) Hardware-Bring-up-Sequenzer")
    parser.add_argument("--iface", default=None, help="Ethernet-Interface fuer DDS (z. B. enp3s0)")
    parser.add_argument(
        "--phase",
        action="append",
        choices=["all", "0", "1", "2", "3", "4"],
        default=None,
        help="Auszufuehrende Phase(n); mehrfach angebbar oder 'all' (Standard: all)",
    )
    parser.add_argument("--endpoint", default=None, help="OPC-UA-Endpunkt fuer Phase 4, z. B. opc.tcp://192.168.100.1:4840")
    parser.add_argument(
        "--enable-commanding",
        action="store_true",
        default=False,
        help="Gelenkansteuerung freigeben (Phase 3) — NUR im aktiven Debug-Modus verwenden!",
    )
    parser.add_argument("--yes", action="store_true", default=False, help="Sicherheitsabfragen automatisch bestaetigen")
    parser.add_argument("--mainboard-ip", default=_DEFAULT_MAINBOARD_IP, help="IP des H2-Mainboards fuer Phase 0")
    args = parser.parse_args(argv)

    phase_args = args.phase or ["all"]
    phases = [0, 1, 2, 3, 4] if "all" in phase_args else sorted({int(p) for p in phase_args})

    if args.enable_commanding:
        _log.warning(
            "main: --enable-commanding aktiv — Phase 3 kann echte Gelenkbewegungen ausloesen. "
            "NUR im aktiven Debug-Modus an der Fernbedienung verwenden!"
        )

    driver = UnitreeSdkDriver(network_interface=args.iface, enable_commanding=args.enable_commanding)
    sink = LocoClientVelocitySink(network_interface=args.iface)

    handshake: H2HandshakeClient | None = None
    if args.endpoint:
        handshake = H2HandshakeClient(transport=AsyncuaTransport(args.endpoint))
    elif 4 in phases:
        _log.error("Phase 4 angefordert, aber kein --endpoint angegeben — abgebrochen")
        return 1

    safety = SafetyGate()
    safety.reset()

    sequencer = BringupSequencer(
        driver=driver,
        sink=sink,
        handshake=handshake,
        safety=safety,
        network_interface=args.iface,
        mainboard_ip=args.mainboard_ip,
    )
    ok = sequencer.run(phases, assume_yes=args.yes)
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
