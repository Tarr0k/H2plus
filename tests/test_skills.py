"""Skill-/Orchestrator-Tests: Lade-Sequenz mit gemockter SPS + Sim-Treiber."""

from __future__ import annotations

from pathlib import Path

from h2_loader.core.orchestrator import Orchestrator
from h2_loader.motion.teach_replay import TeachReplayPlanner
from h2_loader.plc.signals import Signal
from h2_loader.skills.base import SkillContext
from h2_loader.skills.load_workpiece import LoadWorkpieceSkill

POSES_DIR = Path(__file__).resolve().parents[1] / "config" / "poses"


def _ctx(sim_robot, plc) -> SkillContext:
    return SkillContext(robot=sim_robot, motion=TeachReplayPlanner(sim_robot, POSES_DIR), plc=plc)


def test_load_skill_succeeds_when_preconditions_met(sim_robot, mock_plc) -> None:
    skill = LoadWorkpieceSkill(_ctx(sim_robot, mock_plc))
    assert skill.precondition() is True
    assert skill.execute() is True
    # Skill meldet ROBOT_DONE an die SPS.
    assert mock_plc.read_signal(Signal.ROBOT_DONE) is True


def test_load_skill_blocked_without_preconditions(sim_robot, mock_plc) -> None:
    mock_plc.state[Signal.FIXTURE_FREE] = False
    skill = LoadWorkpieceSkill(_ctx(sim_robot, mock_plc))
    assert skill.precondition() is False


def test_orchestrator_ticks_sequence(sim_robot, mock_plc) -> None:
    skill = LoadWorkpieceSkill(_ctx(sim_robot, mock_plc))
    orch = Orchestrator([skill])
    assert orch.tick_once() is True


def test_orchestrator_stops_on_failed_precondition(sim_robot, mock_plc) -> None:
    mock_plc.state[Signal.DOOR_OPEN] = False
    skill = LoadWorkpieceSkill(_ctx(sim_robot, mock_plc))
    orch = Orchestrator([skill])
    assert orch.tick_once() is False
