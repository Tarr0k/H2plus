"""Tests für ScrewdriverEndEffector, ToolChanger und ChangeInductorSkill."""

from __future__ import annotations

from pathlib import Path

import pytest

from h2_loader.core.job_runner import JobRunner
from h2_loader.hal.arm import Arm
from h2_loader.hal.drivers.mujoco_sim_driver import MujocoSimDriver
from h2_loader.hal.end_effector.pneumatic_gripper import PneumaticGripper
from h2_loader.hal.end_effector.screwdriver import ScrewdriverEndEffector
from h2_loader.hal.end_effector.valve_actuator import H2IoValveActuator
from h2_loader.hal.robot import Robot
from h2_loader.hal.tool_changer import ToolChanger
from h2_loader.motion.teach_replay import TeachReplayPlanner
from h2_loader.plc.udt import JobRequest, JobResult
from h2_loader.skills.base import SkillContext
from h2_loader.skills.change_inductor import ChangeInductorSkill

POSES_DIR = Path(__file__).resolve().parents[1] / "config" / "poses"


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _make_robot_with_gripper() -> tuple[Robot, PneumaticGripper]:
    """Erzeugt einen Sim-Roboter und gibt den rechten Greifer zurück."""
    driver = MujocoSimDriver()
    right_gripper = PneumaticGripper(H2IoValveActuator(channel=1))
    arms = {
        "left":  Arm("left",  driver, PneumaticGripper(H2IoValveActuator(channel=0))),
        "right": Arm("right", driver, right_gripper),
    }
    robot = Robot(driver, arms)
    robot.connect()
    return robot, right_gripper


def _make_tool_changer(robot: Robot, right_gripper: PneumaticGripper) -> ToolChanger:
    return ToolChanger(
        robot,
        tools={
            "gripper":     right_gripper,
            "screwdriver": ScrewdriverEndEffector(label="test_screwdriver"),
        },
        default_tool="gripper",
    )


def _ctx(robot, machine, locomotion, tool_changer=None) -> SkillContext:
    return SkillContext(
        robot=robot,
        motion=TeachReplayPlanner(robot, POSES_DIR),
        machine=machine,
        locomotion=locomotion,
        tool_changer=tool_changer,
    )


# ---------------------------------------------------------------------------
# ScrewdriverEndEffector
# ---------------------------------------------------------------------------

class TestScrewdriverEndEffector:
    """Grundlegende Funktionalität des Schrauber-Endeffektors."""

    def test_loosen_runs_without_error(self) -> None:
        sd = ScrewdriverEndEffector()
        sd.loosen()
        sd.loosen(turns=2.5)

    def test_tighten_runs_without_error(self) -> None:
        sd = ScrewdriverEndEffector()
        sd.tighten()
        sd.tighten(turns=3.0)

    def test_grasp_sets_holding(self) -> None:
        sd = ScrewdriverEndEffector()
        assert sd.is_holding() is False
        sd.grasp()
        assert sd.is_holding() is True

    def test_release_clears_holding(self) -> None:
        sd = ScrewdriverEndEffector()
        sd.grasp()
        sd.release()
        assert sd.is_holding() is False

    def test_grasp_release_cycle(self) -> None:
        sd = ScrewdriverEndEffector()
        sd.grasp()
        sd.loosen(turns=1.0)
        sd.tighten(turns=1.0)
        sd.release()
        assert sd.is_holding() is False


# ---------------------------------------------------------------------------
# ToolChanger
# ---------------------------------------------------------------------------

class TestToolChanger:
    """Werkzeugwechsel-Logik."""

    def test_equip_screwdriver_changes_end_effector(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, right_gripper)

        assert isinstance(robot.arm("right").end_effector, PneumaticGripper)
        tc.equip("right", "screwdriver")
        assert isinstance(robot.arm("right").end_effector, ScrewdriverEndEffector)

    def test_equip_gripper_restores_gripper(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, right_gripper)

        tc.equip("right", "screwdriver")
        tc.equip("right", "gripper")
        assert isinstance(robot.arm("right").end_effector, PneumaticGripper)

    def test_equip_unknown_tool_raises_key_error(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, right_gripper)

        with pytest.raises(KeyError):
            tc.equip("right", "laser_cutter")

    def test_equip_same_tool_twice_no_error(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, right_gripper)

        # Zweimal Greifer — kein Fehler, Meldung "bereits aktiv"
        tc.equip("right", "gripper")
        tc.equip("right", "gripper")
        assert isinstance(robot.arm("right").end_effector, PneumaticGripper)

    def test_current_tool_initial_is_default(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, right_gripper)

        assert tc.current_tool("right") == "gripper"

    def test_current_tool_after_equip(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, right_gripper)

        tc.equip("right", "screwdriver")
        assert tc.current_tool("right") == "screwdriver"

    def test_default_tool_not_in_tools_raises(self) -> None:
        robot, right_gripper = _make_robot_with_gripper()
        with pytest.raises(KeyError):
            ToolChanger(
                robot,
                tools={"screwdriver": ScrewdriverEndEffector()},
                default_tool="gripper",  # nicht vorhanden
            )


# ---------------------------------------------------------------------------
# ChangeInductorSkill — precondition
# ---------------------------------------------------------------------------

class TestChangeInductorPrecondition:
    """Vorbedingungs-Tests."""

    def test_precondition_false_without_tool_changer(
        self, plc_env, sim_robot, sim_locomotion
    ) -> None:
        plc_env.simulator.send_job(JobRequest.CHANGE_INDUCTOR, job_id=1)
        skill = ChangeInductorSkill(_ctx(sim_robot, plc_env.machine, sim_locomotion))
        assert skill.precondition() is False

    def test_precondition_false_machine_not_ready(
        self, sim_robot, sim_locomotion, plc_env
    ) -> None:
        # Kein send_job → machineReady=False
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))
        assert skill.precondition() is False

    def test_precondition_false_door_closed(
        self, sim_robot, sim_locomotion, plc_env
    ) -> None:
        # machineReady=True, aber doorOpen=False
        plc_env.handshake.write("plcToRobot", "machineReady", True)
        plc_env.handshake.write("plcToRobot", "doorOpen", False)
        plc_env.handshake.write("plcToRobot", "machineCycleRun", False)
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))
        assert skill.precondition() is False

    def test_precondition_false_cycle_running(
        self, sim_robot, sim_locomotion, plc_env
    ) -> None:
        plc_env.handshake.write("plcToRobot", "machineReady",    True)
        plc_env.handshake.write("plcToRobot", "doorOpen",        True)
        plc_env.handshake.write("plcToRobot", "machineCycleRun", True)
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))
        assert skill.precondition() is False

    def test_precondition_true_all_conditions_met(
        self, sim_robot, sim_locomotion, plc_env
    ) -> None:
        plc_env.simulator.send_job(JobRequest.CHANGE_INDUCTOR, job_id=2)
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))
        assert skill.precondition() is True


# ---------------------------------------------------------------------------
# ChangeInductorSkill — execute
# ---------------------------------------------------------------------------

class TestChangeInductorExecute:
    """Vollständiger Durchlauf von execute()."""

    def test_execute_returns_true(self, sim_locomotion, plc_env) -> None:
        plc_env.simulator.send_job(JobRequest.CHANGE_INDUCTOR, job_id=3)
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))

        assert skill.precondition() is True
        result = skill.execute()
        assert result is True

    def test_active_tool_is_gripper_after_execute(self, sim_locomotion, plc_env) -> None:
        """Nach execute() muss der Greifer wieder aktiv sein."""
        plc_env.simulator.send_job(JobRequest.CHANGE_INDUCTOR, job_id=4)
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))

        skill.execute()
        assert tc.current_tool("right") == "gripper"
        assert isinstance(robot.arm("right").end_effector, PneumaticGripper)

    def test_execute_with_motion_planner(self, sim_locomotion, plc_env) -> None:
        """execute() ohne Policy — TeachReplayPlanner übernimmt Bewegung."""
        plc_env.simulator.send_job(JobRequest.CHANGE_INDUCTOR, job_id=5)
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        skill = ChangeInductorSkill(_ctx(robot, plc_env.machine, sim_locomotion, tc))
        assert skill.execute() is True


# ---------------------------------------------------------------------------
# JobRunner-Dispatch
# ---------------------------------------------------------------------------

class TestJobRunnerChangeInductor:
    """CHANGE_INDUCTOR-Auftrag über den JobRunner."""

    def test_change_inductor_cycle_ok(self, sim_locomotion, plc_env) -> None:
        robot, gripper = _make_robot_with_gripper()
        tc = _make_tool_changer(robot, gripper)
        ctx = _ctx(robot, plc_env.machine, sim_locomotion, tc)
        skills: dict[JobRequest, object] = {
            JobRequest.LOAD:            __import__(
                "h2_loader.skills.load_workpiece", fromlist=["LoadWorkpieceSkill"]
            ).LoadWorkpieceSkill(ctx),
            JobRequest.UNLOAD:          __import__(
                "h2_loader.skills.unload_workpiece", fromlist=["UnloadWorkpieceSkill"]
            ).UnloadWorkpieceSkill(ctx),
            JobRequest.CHANGE_INDUCTOR: ChangeInductorSkill(ctx),
        }
        runner = JobRunner(plc_env.handshake, skills)  # type: ignore[arg-type]

        outcome = plc_env.simulator.run_cycle(runner, JobRequest.CHANGE_INDUCTOR, job_id=10)

        assert outcome is not None
        assert outcome.result == JobResult.OK
        assert outcome.skill_ran is True
        assert outcome.request == JobRequest.CHANGE_INDUCTOR
