"""Tests für den GR00T-Ein-/Ausgabe-Adapter in GrootPolicy (ADR-0007, Stufe 3)."""

from __future__ import annotations

import pytest

from h2_loader.policy.base import Observation
from h2_loader.policy.groot_policy import GrootPolicy


def test_observation_to_groot_maps_state_and_task() -> None:
    """_observation_to_groot liefert state.right_arm (7 Werte) und die Task-Description."""
    policy = GrootPolicy(arm="right")
    obs = Observation(goal="load", joint_state={"right": [0.1] * 7})
    groot_input = policy._observation_to_groot(obs)
    assert len(groot_input["state.right_arm"]) == 7
    assert groot_input["annotation.human.task_description"] == "load"


def test_observation_to_groot_defaults_without_joint_state() -> None:
    """Ohne joint_state liefert der Adapter Nullen statt eines Fehlers."""
    policy = GrootPolicy(arm="right")
    groot_input = policy._observation_to_groot(Observation())
    assert groot_input["state.right_arm"] == [0.0] * 7
    assert groot_input["annotation.human.task_description"] == ""


def test_groot_action_to_action_maps_seven_joints() -> None:
    """_groot_action_to_action baut eine Action mit 7 Gelenkwinkeln ohne Greiferinfo."""
    policy = GrootPolicy(arm="right")
    action = policy._groot_action_to_action([0.0] * 7)
    assert action.arm == "right"
    assert len(action.joint_targets) == 7
    assert action.gripper_closed is None


def test_groot_action_to_action_with_gripper_threshold() -> None:
    """Ein 8. Wert wird als Greifer-Zustand mit Schwelle 0.5 interpretiert."""
    policy = GrootPolicy(arm="right")
    closed = policy._groot_action_to_action([0.0] * 7 + [0.9])
    opened = policy._groot_action_to_action([0.0] * 7 + [0.1])
    assert closed.gripper_closed is True
    assert opened.gripper_closed is False


def test_groot_action_to_action_wrong_length_raises() -> None:
    """Eine falsche Länge des GR00T-Action-Vektors wird als Fehler behandelt."""
    policy = GrootPolicy(arm="right")
    with pytest.raises(ValueError):
        policy._groot_action_to_action([0.0] * 5)


def test_predict_still_raises_not_implemented() -> None:
    """predict() bleibt an der Inferenzgrenze (NotImplementedError), Mapping läuft vorher."""
    policy = GrootPolicy(arm="right")
    with pytest.raises(NotImplementedError, match="GR00T-Inferenz"):
        policy.predict(Observation(goal="load"))
