"""HAL-Tests: Greifer und Arm gegen den Sim-Treiber (keine echte Hardware)."""

from __future__ import annotations

import pytest

from h2_loader.hal.end_effector.pneumatic_gripper import PneumaticGripper
from h2_loader.hal.end_effector.valve_actuator import H2IoValveActuator


def test_gripper_grasp_release_tracks_state() -> None:
    gripper = PneumaticGripper(H2IoValveActuator(channel=0))
    assert gripper.is_holding() is False
    gripper.grasp()
    assert gripper.is_holding() is True
    gripper.release()
    assert gripper.is_holding() is False


def test_arm_move_sets_driver_state(sim_robot) -> None:
    arm = sim_robot.arm("right")
    target = [0.1, 0.2, 0.0, -0.5, 0.0, 0.3, 0.0]
    arm.move_joints(target)
    assert arm.current_joints() == target


def test_arm_rejects_wrong_dof(sim_robot) -> None:
    with pytest.raises(ValueError):
        sim_robot.arm("left").move_joints([0.0, 0.0, 0.0])


def test_robot_unknown_side_raises(sim_robot) -> None:
    with pytest.raises(KeyError):
        sim_robot.arm("middle")
