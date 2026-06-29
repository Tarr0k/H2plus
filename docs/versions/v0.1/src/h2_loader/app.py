"""Einstiegspunkt: Config laden -> Komponenten verdrahten -> Orchestrator ticken.

Dies ist der *Composition Root*: die einzige Stelle, an der konkrete Treiber
ausgewählt und zusammengesteckt werden. Skills und Core kennen nur Interfaces —
hier fällt die Entscheidung Sim vs. reale HW (per ``--driver`` bzw. robot.yaml)
und welcher Ventil-Aktor/Endeffektor injiziert wird.

Stub-Stand: tickt die Lade-Sequenz einmal durch (die unteren Schichten loggen
ihre Schritte) und terminiert sauber. Keine echte Roboterbewegung.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .core.orchestrator import Orchestrator
from .core.safety import SafetyGate
from .hal.arm import Arm
from .hal.drivers.base import RobotDriverInterface
from .hal.drivers.mujoco_sim_driver import MujocoSimDriver
from .hal.drivers.unitree_sdk_driver import UnitreeSdkDriver
from .hal.end_effector.pneumatic_gripper import PneumaticGripper
from .hal.end_effector.valve_actuator import H2IoValveActuator
from .hal.robot import Robot
from .motion.teach_replay import TeachReplayPlanner
from .plc.opcua_client import OpcUaPlcClient
from .plc.signals import Signal
from .skills.base import SkillContext
from .skills.load_workpiece import LoadWorkpieceSkill
from .util.config import PlcConfig, RobotConfig
from .util.logging import get_logger

_log = get_logger(__name__)


def build_driver(name: str) -> RobotDriverInterface:
    """Wählt den Lowlevel-Treiber anhand des Namens ("sim"|"sdk")."""
    if name == "sim":
        return MujocoSimDriver()
    if name == "sdk":
        return UnitreeSdkDriver()
    raise ValueError(f"Unbekannter Treiber: {name!r} (erwartet 'sim' oder 'sdk')")


def build_robot(driver: RobotDriverInterface) -> Robot:
    """Verdrahtet beide Arme mit je einem Pneumatikgreifer.

    Im ersten Ausbau wird der Greifer über die bordeigene H2-IO geschaltet
    (``H2IoValveActuator``). Die Wahl SPS vs. H2-IO ist hier zentralisiert und
    austauschbar (siehe ADR-0002).
    """
    arms = {
        side: Arm(side, driver, PneumaticGripper(H2IoValveActuator(channel=ch)))
        for side, ch in (("left", 0), ("right", 1))
    }
    return Robot(driver, arms)


def build_orchestrator(robot: Robot, plc: OpcUaPlcClient, poses_dir: Path) -> Orchestrator:
    """Baut den Skill-Kontext und die Skill-Sequenz."""
    motion = TeachReplayPlanner(robot, poses_dir)
    ctx = SkillContext(robot=robot, motion=motion, plc=plc)
    skills = [LoadWorkpieceSkill(ctx)]
    return Orchestrator(skills, safety=SafetyGate())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="h2-loader", description="H2 PLUS Maschinenlader (Gerüst)")
    parser.add_argument("--config", default="config/robot.yaml", help="Pfad zur robot.yaml")
    parser.add_argument("--plc-config", default="config/plc.yaml", help="Pfad zur plc.yaml")
    parser.add_argument("--driver", choices=["sim", "sdk"], default=None,
                        help="Treiber überschreiben (sonst aus robot.yaml)")
    parser.add_argument("--poses-dir", default="config/poses", help="Verzeichnis der angelernten Posen")
    args = parser.parse_args(argv)

    robot_cfg = RobotConfig.load(args.config)
    driver_name = args.driver or robot_cfg.driver
    _log.info("Starte h2_loader mit Treiber '%s'", driver_name)

    driver = build_driver(driver_name)
    robot = build_robot(driver)

    plc_cfg = PlcConfig.load(args.plc_config) if Path(args.plc_config).is_file() else PlcConfig()
    plc = OpcUaPlcClient(endpoint=plc_cfg.endpoint, node_map={k: str(v) for k, v in plc_cfg.signals.items()})

    robot.connect()
    plc.connect()

    # Sim-Dry-Run ohne reale Maschine: "Maschine bereit"-Signale vorbelegen, damit die
    # Lade-Sequenz die Vorbedingung passiert und alle Schritte demonstriert. Niemals bei 'sdk'.
    if driver_name == "sim":
        _log.info("Sim-Modus: Demo-SPS-Signale vorbelegen (DOOR_OPEN, FIXTURE_FREE)")
        plc.write_signal(Signal.DOOR_OPEN, True)
        plc.write_signal(Signal.FIXTURE_FREE, True)

    try:
        orch = build_orchestrator(robot, plc, Path(args.poses_dir))
        ok = orch.tick_once()
    finally:
        plc.disconnect()
        robot.disconnect()

    _log.info("h2_loader beendet (Ergebnis=%s)", "OK" if ok else "FEHLER/Vorbedingung")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
