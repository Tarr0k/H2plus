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

from .core.job_runner import JobRunner
from .core.orchestrator import Orchestrator
from .core.safety import SafetyGate, SafetySupervisor
from .hal.arm import Arm
from .hal.drivers.base import RobotDriverInterface
from .hal.drivers.mujoco_sim_driver import MujocoSimDriver
from .hal.drivers.unitree_sdk_driver import UnitreeSdkDriver
from .hal.end_effector.pneumatic_gripper import PneumaticGripper
from .hal.end_effector.valve_actuator import H2IoValveActuator
from .hal.locomotion.onboard_locomotion import OnboardLocomotion
from .hal.locomotion.safety_monitored import SafetyMonitoredLocomotion
from .hal.robot import Robot
from .motion.teach_replay import TeachReplayPlanner
from .plc.handshake import H2HandshakeClient
from .plc.machine_io import MachineIo
from .plc.plc_simulator import PlcSimulator
from .plc.udt import JobRequest, JobResult
from .skills.base import SkillContext
from .skills.load_workpiece import LoadWorkpieceSkill
from .skills.unload_workpiece import UnloadWorkpieceSkill
from .util.config import PlcConfig, RobotConfig, SafetyConfig, StationsConfig
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


def build_orchestrator(
    robot: Robot,
    machine: MachineIo,
    poses_dir: Path,
    locomotion: OnboardLocomotion,
) -> Orchestrator:
    """Baut den Skill-Kontext und die Skill-Sequenz."""
    motion = TeachReplayPlanner(robot, poses_dir)
    ctx = SkillContext(robot=robot, motion=motion, machine=machine, locomotion=locomotion)
    skills = [LoadWorkpieceSkill(ctx)]
    return Orchestrator(skills, safety=SafetyGate())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="h2-loader", description="H2 PLUS Maschinenlader (Gerüst)")
    parser.add_argument("--config", default="config/robot.yaml", help="Pfad zur robot.yaml")
    parser.add_argument("--plc-config", default="config/plc.yaml", help="Pfad zur plc.yaml")
    parser.add_argument("--stations-config", default="config/stations.yaml",
                        help="Pfad zur stations.yaml")
    parser.add_argument("--driver", choices=["sim", "sdk"], default=None,
                        help="Treiber überschreiben (sonst aus robot.yaml)")
    parser.add_argument("--poses-dir", default="config/poses", help="Verzeichnis der angelernten Posen")
    parser.add_argument(
        "--safety-config",
        default="config/safety_zones.yaml",
        help="Pfad zur safety_zones.yaml (funktionales Zonenmodell)",
    )
    args = parser.parse_args(argv)

    robot_cfg = RobotConfig.load(args.config)
    driver_name = args.driver or robot_cfg.driver
    _log.info("Starte h2_loader mit Treiber '%s'", driver_name)

    driver = build_driver(driver_name)
    robot = build_robot(driver)

    plc_cfg = PlcConfig.load(args.plc_config) if Path(args.plc_config).is_file() else PlcConfig()

    # Stationskarte laden; bei fehlender Datei leere Karte (kein Fehler beim Start)
    stations_cfg = (
        StationsConfig.load(args.stations_config)
        if Path(args.stations_config).is_file()
        else StationsConfig()
    )

    # Safety-Zonenmodell laden (optional; bei fehlender Datei leeres Modell)
    safety_cfg = (
        SafetyConfig.load(args.safety_config)
        if Path(args.safety_config).is_file()
        else SafetyConfig()
    )

    robot.connect()

    handshake = H2HandshakeClient(
        db_name=plc_cfg.udt.get("db_name", "H2_Interface_DB"),
        ns=int(plc_cfg.udt.get("namespace_index", 3)),
    )

    # Supervisor aufbauen (handshake muss vor supervisor gebaut sein)
    supervisor = SafetySupervisor(
        handshake=handshake,
        zones=safety_cfg.zones,
        station_zone=safety_cfg.station_zone,
    )

    # Locomotion mit Safety-Wrapper umhüllen
    locomotion: SafetyMonitoredLocomotion = SafetyMonitoredLocomotion(
        OnboardLocomotion(stations_cfg.stations, driver),
        supervisor,
    )

    motion = TeachReplayPlanner(robot, Path(args.poses_dir))

    try:
        if driver_name == "sim":
            # Vollständiger Zyklus über Job-Dispatch-Ebene: SPS sendet LOAD-Auftrag,
            # Roboter nimmt an, führt Skill aus, meldet fertig.
            sim = PlcSimulator(handshake)
            machine = MachineIo(handshake, responder=sim.service_requests)
            ctx = SkillContext(robot=robot, motion=motion, machine=machine, locomotion=locomotion)
            skills: dict[JobRequest, object] = {
                JobRequest.LOAD: LoadWorkpieceSkill(ctx),
                JobRequest.UNLOAD: UnloadWorkpieceSkill(ctx),
            }
            runner = JobRunner(handshake, skills, safety=supervisor)  # type: ignore[arg-type]
            outcome = sim.run_cycle(runner, JobRequest.LOAD, job_id=1, part_type=0)
            if outcome is not None:
                _log.info(
                    "Sim-Zyklus abgeschlossen: jobId=%d request=%s result=%s skill_ran=%s",
                    outcome.job_id,
                    outcome.request.name,
                    outcome.result.name,
                    outcome.skill_ran,
                )
            ok = outcome is not None and outcome.result == JobResult.OK
        else:
            # Live-Modus: keine automatischen Aufträge senden — SPS übernimmt
            _log.info("SDK-Modus: warte auf SPS-Aufträge (Live-Modus, kein Sim-Auftrag)")
            machine = MachineIo(handshake)
            ok = True
    finally:
        robot.disconnect()

    _log.info("h2_loader beendet (Ergebnis=%s)", "OK" if ok else "FEHLER/Vorbedingung")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
