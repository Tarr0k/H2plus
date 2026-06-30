"""Skill-/Orchestrator-Tests: Lade-/Entlade-Sequenz mit UDT-Simulator."""

from __future__ import annotations

from pathlib import Path

from h2_loader.core.orchestrator import Orchestrator
from h2_loader.motion.teach_replay import TeachReplayPlanner
from h2_loader.plc.udt import JobRequest
from h2_loader.skills.base import SkillContext
from h2_loader.skills.load_workpiece import LoadWorkpieceSkill
from h2_loader.skills.unload_workpiece import UnloadWorkpieceSkill

POSES_DIR = Path(__file__).resolve().parents[1] / "config" / "poses"


def _ctx(sim_robot, machine, locomotion) -> SkillContext:
    return SkillContext(
        robot=sim_robot,
        motion=TeachReplayPlanner(sim_robot, POSES_DIR),
        machine=machine,
        locomotion=locomotion,
    )


def test_load_skill_succeeds_when_preconditions_met(plc_env, sim_robot, sim_locomotion) -> None:
    plc_env.simulator.send_job(JobRequest.LOAD, job_id=1)
    skill = LoadWorkpieceSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
    assert skill.precondition() is True
    result = skill.execute()
    assert result is True
    # Nach execute: Spannvorrichtung muss geschlossen sein (Clamp-Handshake)
    assert plc_env.machine.clamp_closed() is True


def test_load_skill_blocked_without_preconditions(plc_env, sim_robot, sim_locomotion) -> None:
    # Kein send_job → Standardzustand: doorOpen=False, partInClamp=False
    # partInClamp=False → fixture_free=True, aber doorOpen=False → precondition False
    skill = LoadWorkpieceSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
    assert skill.precondition() is False


def test_load_skill_blocked_when_fixture_occupied(plc_env, sim_robot, sim_locomotion) -> None:
    # UNLOAD-Seed: partInClamp=True → fixture_free=False → precondition False
    plc_env.simulator.send_job(JobRequest.UNLOAD, job_id=2)
    skill = LoadWorkpieceSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
    assert skill.precondition() is False


def test_unload_skill_succeeds_when_preconditions_met(plc_env, sim_robot, sim_locomotion) -> None:
    plc_env.simulator.send_job(JobRequest.UNLOAD, job_id=3)
    skill = UnloadWorkpieceSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
    assert skill.precondition() is True
    result = skill.execute()
    assert result is True
    # Nach execute: Greifer hat abgelegt, gripperHoldsPart=False
    assert plc_env.machine.part_in_clamp() is False


def test_orchestrator_ticks_sequence(plc_env, sim_robot, sim_locomotion) -> None:
    plc_env.simulator.send_job(JobRequest.LOAD, job_id=4)
    skill = LoadWorkpieceSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
    orch = Orchestrator([skill])
    assert orch.tick_once() is True


def test_orchestrator_stops_on_failed_precondition(plc_env, sim_robot, sim_locomotion) -> None:
    # Kein Seeding: doorOpen=False → precondition False
    skill = LoadWorkpieceSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
    orch = Orchestrator([skill])
    assert orch.tick_once() is False
