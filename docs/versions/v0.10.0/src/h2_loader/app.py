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
from .hal.end_effector.screwdriver import ScrewdriverEndEffector
from .hal.end_effector.valve_actuator import H2IoValveActuator
from .hal.tool_changer import ToolChanger
from .hal.locomotion.localization import Pose2D, SimLocalization
from .hal.locomotion.navigating_locomotion import NavigatingLocomotion
from .hal.locomotion.onboard_locomotion import OnboardLocomotion
from .hal.locomotion.safety_monitored import SafetyMonitoredLocomotion
from .hal.locomotion.velocity_sink import LocoClientVelocitySink, SimVelocitySink
from .hal.robot import Robot
from .motion.teach_replay import TeachReplayPlanner
from .plc.handshake import H2HandshakeClient
from .plc.machine_io import MachineIo
from .plc.plc_simulator import PlcSimulator
from .plc.udt import JobRequest, JobResult
from .policy.base import PolicyInterface
from .policy.fallback import FallbackPolicy
from .policy.groot_policy import GrootPolicy
from .policy.safeguard import SafeguardedPolicy
from .policy.scripted_policy import ScriptedPolicy
from .skills.base import SkillContext
from .skills.change_inductor import ChangeInductorSkill
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


def build_robot(driver: RobotDriverInterface) -> tuple[Robot, dict[str, PneumaticGripper]]:
    """Verdrahtet beide Arme mit je einem Pneumatikgreifer.

    Im ersten Ausbau wird der Greifer über die bordeigene H2-IO geschaltet
    (``H2IoValveActuator``). Die Wahl SPS vs. H2-IO ist hier zentralisiert und
    austauschbar (siehe ADR-0002).

    Returns:
        Tupel (Robot, grippers) — grippers enthält die Greifer-Instanzen je Seite,
        damit ``build_tool_changer`` darauf zugreifen kann.
    """
    grippers: dict[str, PneumaticGripper] = {
        side: PneumaticGripper(H2IoValveActuator(channel=ch))
        for side, ch in (("left", 0), ("right", 1))
    }
    arms = {side: Arm(side, driver, grippers[side]) for side in grippers}
    return Robot(driver, arms), grippers


def build_tool_changer(robot: Robot, right_gripper: PneumaticGripper) -> ToolChanger:
    """Baut den ToolChanger für den rechten Arm (CHANGE_INDUCTOR-Skill).

    Der Greifer im tools-Dict muss identisch mit der Greifer-Instanz des Arms
    sein, damit ``equip("gripper")`` denselben Endeffektor zurücksetzt, der
    initial montiert ist.

    Args:
        robot:         Roboter-Fassade.
        right_gripper: Greifer-Instanz des rechten Arms.

    Returns:
        Konfigurierter ``ToolChanger`` (gripper + screwdriver, default gripper).
    """
    return ToolChanger(
        robot,
        tools={
            "gripper":     right_gripper,
            "screwdriver": ScrewdriverEndEffector(label="screwdriver_right"),
        },
        default_tool="gripper",
    )


def build_policy(
    policy_name: str,
    poses_dir: Path,
    robot_cfg: RobotConfig,
) -> PolicyInterface:
    """Baut die Policy anhand des gewählten Backends und wickelt sie in SafeguardedPolicy.

    Args:
        policy_name: "scripted" oder "groot".
        poses_dir:   Verzeichnis mit den angelernten Posen (für ScriptedPolicy).
        robot_cfg:   Roboter-Konfiguration (Gelenkgrenzen aus ``arms``).

    Returns:
        ``SafeguardedPolicy`` um die gewählte Inner-Policy.
    """
    # Gelenkgrenzen aus robot.yaml aufbauen: {arm: (lower, upper)}
    limits: dict[str, tuple[list[float], list[float]]] = {}
    for side, arm_cfg in robot_cfg.arms.items():
        lower = arm_cfg.get("joint_limits_lower", [])
        upper = arm_cfg.get("joint_limits_upper", [])
        limits[side] = (lower, upper)

    if policy_name == "scripted":
        inner: PolicyInterface = ScriptedPolicy(poses_dir)
    elif policy_name == "groot":
        inner = FallbackPolicy(
            primary=GrootPolicy(),
            fallback=ScriptedPolicy(poses_dir),
        )
    else:
        raise ValueError(f"Unbekanntes Policy-Backend: {policy_name!r}")

    return SafeguardedPolicy(inner, limits)


def build_orchestrator(
    robot: Robot,
    machine: MachineIo,
    poses_dir: Path,
    locomotion: SafetyMonitoredLocomotion,
) -> Orchestrator:
    """Baut den Skill-Kontext und die Skill-Sequenz."""
    motion = TeachReplayPlanner(robot, poses_dir)
    ctx = SkillContext(robot=robot, motion=motion, machine=machine, locomotion=locomotion)
    skills = [LoadWorkpieceSkill(ctx)]
    return Orchestrator(skills, safety=SafetyGate())


# Mapping von CLI-Argument-Namen auf JobRequest-Werte
_JOB_MAP: dict[str, JobRequest] = {
    "load":             JobRequest.LOAD,
    "unload":           JobRequest.UNLOAD,
    "change_inductor":  JobRequest.CHANGE_INDUCTOR,
}


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
    parser.add_argument(
        "--policy",
        choices=["scripted", "groot"],
        default="scripted",
        help="Policy-Backend: 'scripted' (Teach-in, deterministisch) oder "
             "'groot' (GR00T N1.7-Stub, fällt auf scripted zurück)",
    )
    parser.add_argument(
        "--job",
        choices=list(_JOB_MAP.keys()),
        default="load",
        help="Sim-Auftrag: 'load' (Standard), 'unload' oder 'change_inductor'",
    )
    args = parser.parse_args(argv)

    robot_cfg = RobotConfig.load(args.config)
    driver_name = args.driver or robot_cfg.driver
    _log.info("Starte h2_loader mit Treiber '%s'", driver_name)

    poses_dir = Path(args.poses_dir)
    policy = build_policy(args.policy, poses_dir, robot_cfg)
    _log.info("Policy: %s", policy.name)

    driver = build_driver(driver_name)
    robot, grippers = build_robot(driver)

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

    # Locomotion aufbauen — Sim: NavigatingLocomotion (Closed-Loop-Regler);
    # SDK: OnboardLocomotion-Stub (LocoClient + echte Lokalisierung später).
    if driver_name == "sim":
        # Startpose aus der Home-Station, falls vorhanden.
        if "home" in stations_cfg.stations:
            _home_pos = stations_cfg.stations["home"].position
            _start_pose = Pose2D(*_home_pos)
        else:
            _start_pose = Pose2D()
        _loc = SimLocalization(_start_pose)
        _sink = SimVelocitySink(_loc, dt=stations_cfg.nav.get("dt", 0.1))
        _inner_loco = NavigatingLocomotion(
            stations_cfg.stations, _loc, _sink, nav=stations_cfg.nav
        )
    else:
        # SDK-Pfad: OnboardLocomotion-Stub (LocoClientVelocitySink + echte
        # Lokalisierung werden ergänzt, sobald der LocoClient integriert ist).
        _inner_loco = OnboardLocomotion(stations_cfg.stations, driver)  # type: ignore[assignment]

    locomotion: SafetyMonitoredLocomotion = SafetyMonitoredLocomotion(
        _inner_loco,
        supervisor,
    )

    motion = TeachReplayPlanner(robot, poses_dir)

    try:
        if driver_name == "sim":
            # Vollständiger Zyklus über Job-Dispatch-Ebene: SPS sendet Auftrag,
            # Roboter nimmt an, führt Skill aus, meldet fertig.
            sim = PlcSimulator(handshake)
            machine = MachineIo(handshake, responder=sim.service_requests)
            tool_changer = build_tool_changer(robot, grippers["right"])
            ctx = SkillContext(
                robot=robot,
                motion=motion,
                machine=machine,
                locomotion=locomotion,
                policy=policy,
                tool_changer=tool_changer,
            )
            skills: dict[JobRequest, object] = {
                JobRequest.LOAD:             LoadWorkpieceSkill(ctx),
                JobRequest.UNLOAD:           UnloadWorkpieceSkill(ctx),
                JobRequest.CHANGE_INDUCTOR:  ChangeInductorSkill(ctx),
            }
            job_req = _JOB_MAP[args.job]
            _log.info("Sim-Auftrag: %s", job_req.name)
            runner = JobRunner(handshake, skills, safety=supervisor)  # type: ignore[arg-type]
            outcome = sim.run_cycle(runner, job_req, job_id=1, part_type=0)
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
