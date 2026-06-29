"""Motion-Tests: teach_replay fährt angelernte Posen über den Sim-Treiber ab."""

from __future__ import annotations

from pathlib import Path

import pytest

from h2_loader.motion.teach_replay import TeachReplayPlanner

POSES_DIR = Path(__file__).resolve().parents[1] / "config" / "poses"


def test_move_to_loads_pose_and_drives_arm(sim_robot) -> None:
    planner = TeachReplayPlanner(sim_robot, POSES_DIR)
    planner.move_to("right", "load_workpiece")
    # Der Sim-Treiber hält den zuletzt gesendeten Zustand.
    assert sim_robot.arm("right").current_joints() == [0.2, 0.4, 0.0, -0.8, 0.0, 0.6, 0.0]


def test_move_to_missing_arm_in_pose_raises(sim_robot) -> None:
    planner = TeachReplayPlanner(sim_robot, POSES_DIR)
    # Pose existiert, hat aber keine Winkel für einen "middle"-Arm.
    with pytest.raises(KeyError):
        planner.move_to("middle", "load_workpiece")


def test_follow_runs_all_waypoints(sim_robot) -> None:
    planner = TeachReplayPlanner(sim_robot, POSES_DIR)
    traj = [[0.0] * 7, [0.1] * 7, [0.2] * 7]
    planner.follow("left", traj)
    assert sim_robot.arm("left").current_joints() == [0.2] * 7
