"""Tests für JobRunner + PlcSimulator: vollständiger Sim-Zyklus ohne reale HW."""

from __future__ import annotations

from pathlib import Path

from h2_loader.core.job_runner import JobOutcome, JobRunner
from h2_loader.motion.teach_replay import TeachReplayPlanner
from h2_loader.plc.handshake import H2HandshakeClient
from h2_loader.plc.machine_io import MachineIo
from h2_loader.plc.plc_simulator import PlcSimulator
from h2_loader.plc.udt import JobRequest, JobResult
from h2_loader.skills.base import SkillContext
from h2_loader.skills.load_workpiece import LoadWorkpieceSkill
from h2_loader.skills.unload_workpiece import UnloadWorkpieceSkill

# Posen-Verzeichnis analog zu test_skills.py
POSES_DIR = Path(__file__).resolve().parents[1] / "config" / "poses"


def _build_skills(sim_robot, machine, locomotion) -> dict[JobRequest, object]:
    """Erzeugt einen gemeinsamen SkillContext + Dispatch-Dict."""
    ctx = SkillContext(
        robot=sim_robot,
        motion=TeachReplayPlanner(sim_robot, POSES_DIR),
        machine=machine,
        locomotion=locomotion,
    )
    return {
        JobRequest.LOAD: LoadWorkpieceSkill(ctx),
        JobRequest.UNLOAD: UnloadWorkpieceSkill(ctx),
    }


def test_full_load_cycle_succeeds(plc_env, sim_robot, sim_locomotion) -> None:
    """Ein vollständiger LOAD-Zyklus liefert OK und invertiert jobDoneToggle."""
    skills = _build_skills(sim_robot, plc_env.machine, sim_locomotion)
    runner = JobRunner(plc_env.handshake, skills)  # type: ignore[arg-type]

    done_before = plc_env.handshake.read("robotToPlc", "jobDoneToggle")

    outcome: JobOutcome | None = plc_env.simulator.run_cycle(runner, JobRequest.LOAD, job_id=1)

    assert outcome is not None
    assert outcome.result == JobResult.OK
    assert outcome.skill_ran is True
    assert outcome.job_id == 1
    assert outcome.request == JobRequest.LOAD

    # jobResult muss OK im Handshake-State stehen
    assert plc_env.handshake.read("robotToPlc", "jobResult") == int(JobResult.OK)
    # jobAckToggle muss dem jobReqToggle entsprechen (Auftrag wurde quittiert)
    assert (
        plc_env.handshake.read("robotToPlc", "jobAckToggle")
        == plc_env.handshake.read("plcToRobot", "jobReqToggle")
    )
    # jobDoneToggle muss invertiert worden sein
    assert plc_env.handshake.read("robotToPlc", "jobDoneToggle") != done_before


def test_step_returns_none_without_job(plc_env, sim_robot, sim_locomotion) -> None:
    """step() liefert None, wenn kein Auftrag vorliegt."""
    skills = _build_skills(sim_robot, plc_env.machine, sim_locomotion)
    runner = JobRunner(plc_env.handshake, skills)  # type: ignore[arg-type]

    result = runner.step()

    assert result is None


def test_unknown_job_results_nok(plc_env, sim_robot, sim_locomotion) -> None:
    """Ein nicht registrierter Auftragstyp (NONE) führt zu NOK und skill_ran=False."""
    skills = _build_skills(sim_robot, plc_env.machine, sim_locomotion)
    runner = JobRunner(plc_env.handshake, skills)  # type: ignore[arg-type]

    plc_env.handshake.sim_plc_send_job(JobRequest.NONE, 9, 0)
    outcome = runner.step()

    assert outcome is not None
    assert outcome.result == JobResult.NOK
    assert outcome.skill_ran is False
    assert outcome.job_id == 9


def test_failed_precondition_results_nok(plc_env, sim_robot, sim_locomotion) -> None:
    """Nicht erfüllte Vorbedingung führt zu NOK; skill_ran ist True (Skill wurde aufgerufen)."""
    skills = _build_skills(sim_robot, plc_env.machine, sim_locomotion)
    runner = JobRunner(plc_env.handshake, skills)  # type: ignore[arg-type]

    # Auftrag ohne Simulator-Seeding senden: doorOpen=False, fixture_free=True
    # → door_open()=False → precondition False
    plc_env.handshake.sim_plc_send_job(JobRequest.LOAD, 2, 0)

    outcome = runner.step()

    assert outcome is not None
    assert outcome.result == JobResult.NOK
    assert outcome.skill_ran is True


def test_heartbeat_increments(plc_env, sim_robot, sim_locomotion) -> None:
    """step() mit Auftrag erhöht robotHeartbeat um genau 1."""
    skills = _build_skills(sim_robot, plc_env.machine, sim_locomotion)
    runner = JobRunner(plc_env.handshake, skills)  # type: ignore[arg-type]

    hb_before = int(plc_env.handshake.read("control", "robotHeartbeat"))

    plc_env.simulator.run_cycle(runner, JobRequest.LOAD, job_id=3)

    hb_after = int(plc_env.handshake.read("control", "robotHeartbeat"))
    assert hb_after == (hb_before + 1) % 65536
