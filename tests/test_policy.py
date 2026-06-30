"""Tests für das Policy-Paket (ADR-0007).

Prüft ScriptedPolicy, GrootPolicy, SafeguardedPolicy und FallbackPolicy
vollständig ohne echten Roboter (In-Memory, deterministisch).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from h2_loader.motion.teach_replay import TeachReplayPlanner
from h2_loader.plc.udt import JobRequest
from h2_loader.policy.base import Action, Observation, PolicyInterface
from h2_loader.policy.fallback import FallbackPolicy
from h2_loader.policy.groot_policy import GrootPolicy
from h2_loader.policy.safeguard import SafeguardedPolicy
from h2_loader.policy.scripted_policy import ScriptedPolicy
from h2_loader.skills.base import SkillContext
from h2_loader.skills.load_workpiece import LoadWorkpieceSkill

POSES_DIR = Path(__file__).resolve().parents[1] / "config" / "poses"

# Gelenkgrenzen analog zu config/robot.yaml (Platzhalterwerte).
_LIMITS_LOWER = [-3.14, -2.50, -3.14, -2.50, -3.14, -1.57, -3.14]
_LIMITS_UPPER = [ 3.14,  2.50,  3.14,  2.50,  3.14,  1.57,  3.14]
_JOINT_LIMITS: dict[str, tuple[list[float], list[float]]] = {
    "left":  (_LIMITS_LOWER, _LIMITS_UPPER),
    "right": (_LIMITS_LOWER, _LIMITS_UPPER),
}


# ---------------------------------------------------------------------------
# ScriptedPolicy
# ---------------------------------------------------------------------------

def test_scripted_policy_predict_returns_action_with_7_joints() -> None:
    """ScriptedPolicy.predict liefert Action mit 7 Gelenkwinkeln aus config/poses."""
    policy = ScriptedPolicy(POSES_DIR, arm="right")
    obs = Observation(goal="load_workpiece")
    action = policy.predict(obs)
    assert action.arm == "right"
    assert len(action.joint_targets) == 7


def test_scripted_policy_predict_correct_values() -> None:
    """Gelenkwinkel der ScriptedPolicy entsprechen dem YAML-Inhalt."""
    policy = ScriptedPolicy(POSES_DIR, arm="right")
    obs = Observation(goal="load_workpiece")
    action = policy.predict(obs)
    # Aus config/poses/load_workpiece.yaml: right: [0.2, 0.4, 0.0, -0.8, 0.0, 0.6, 0.0]
    assert action.joint_targets == pytest.approx([0.2, 0.4, 0.0, -0.8, 0.0, 0.6, 0.0])


def test_scripted_policy_raises_on_missing_goal() -> None:
    """ScriptedPolicy wirft ValueError, wenn obs.goal nicht gesetzt ist."""
    policy = ScriptedPolicy(POSES_DIR)
    with pytest.raises(ValueError, match="obs.goal"):
        policy.predict(Observation(goal=None))


def test_scripted_policy_raises_on_unknown_pose() -> None:
    """ScriptedPolicy wirft FileNotFoundError bei unbekannter Pose."""
    policy = ScriptedPolicy(POSES_DIR)
    with pytest.raises(FileNotFoundError):
        policy.predict(Observation(goal="does_not_exist_pose"))


def test_scripted_policy_left_arm() -> None:
    """ScriptedPolicy liefert korrekte Gelenkwinkel für den linken Arm."""
    policy = ScriptedPolicy(POSES_DIR, arm="left")
    action = policy.predict(Observation(goal="load_workpiece"))
    assert action.arm == "left"
    # Aus config/poses/load_workpiece.yaml: left: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert action.joint_targets == pytest.approx([0.0] * 7)


# ---------------------------------------------------------------------------
# GrootPolicy
# ---------------------------------------------------------------------------

def test_groot_policy_predict_raises_not_implemented() -> None:
    """GrootPolicy.predict wirft NotImplementedError (Stub)."""
    policy = GrootPolicy()
    with pytest.raises(NotImplementedError, match="GR00T-Inferenz"):
        policy.predict(Observation(goal="load_workpiece"))


def test_groot_policy_reset_does_not_raise() -> None:
    """GrootPolicy.reset ist ohne Fehler aufrufbar."""
    policy = GrootPolicy()
    policy.reset()  # kein Fehler erwartet


# ---------------------------------------------------------------------------
# SafeguardedPolicy
# ---------------------------------------------------------------------------

class _OutOfRangePolicy(PolicyInterface):
    """Hilfs-Policy: gibt immer Out-of-Range-Gelenkwinkel zurück."""

    name = "out_of_range"

    def predict(self, obs: Observation) -> Action:  # noqa: ARG002
        # Werte außerhalb beider Grenzen (lower=-3.14, upper=3.14 → ±10 sind zu groß)
        return Action(arm="right", joint_targets=[10.0] * 7)


class _InRangePolicy(PolicyInterface):
    """Hilfs-Policy: gibt immer In-Range-Gelenkwinkel zurück."""

    name = "in_range"

    def predict(self, obs: Observation) -> Action:  # noqa: ARG002
        return Action(arm="right", joint_targets=[0.5, 0.3, 0.1, -0.5, 0.0, 0.4, 0.0])


def test_safeguarded_policy_clamps_out_of_range() -> None:
    """SafeguardedPolicy klemmt Out-of-Range-Werte auf die konfigurierten Grenzen."""
    policy = SafeguardedPolicy(_OutOfRangePolicy(), _JOINT_LIMITS)
    action = policy.predict(Observation())
    for i, val in enumerate(action.joint_targets):
        assert val <= _LIMITS_UPPER[i], f"Gelenk {i}: {val} > upper {_LIMITS_UPPER[i]}"
        assert val >= _LIMITS_LOWER[i], f"Gelenk {i}: {val} < lower {_LIMITS_LOWER[i]}"


def test_safeguarded_policy_leaves_in_range_unchanged() -> None:
    """SafeguardedPolicy lässt In-Range-Werte unverändert."""
    original = [0.5, 0.3, 0.1, -0.5, 0.0, 0.4, 0.0]
    policy = SafeguardedPolicy(_InRangePolicy(), _JOINT_LIMITS)
    action = policy.predict(Observation())
    assert action.joint_targets == pytest.approx(original)


def test_safeguarded_policy_unknown_arm_passthrough() -> None:
    """SafeguardedPolicy reicht Action unverändert durch, wenn Arm nicht in limits."""

    class _UnknownArmPolicy(PolicyInterface):
        name = "unknown_arm"

        def predict(self, obs: Observation) -> Action:  # noqa: ARG002
            return Action(arm="torso", joint_targets=[99.0, 99.0])

    policy = SafeguardedPolicy(_UnknownArmPolicy(), _JOINT_LIMITS)
    action = policy.predict(Observation())
    assert action.joint_targets == pytest.approx([99.0, 99.0])


def test_safeguarded_policy_name_contains_inner_name() -> None:
    """SafeguardedPolicy.name enthält den Namen der Inner-Policy."""
    policy = SafeguardedPolicy(ScriptedPolicy(POSES_DIR), _JOINT_LIMITS)
    assert "scripted" in policy.name


# ---------------------------------------------------------------------------
# FallbackPolicy
# ---------------------------------------------------------------------------

def test_fallback_policy_uses_fallback_when_primary_raises() -> None:
    """FallbackPolicy wechselt auf ScriptedPolicy, wenn GrootPolicy wirft."""
    policy = FallbackPolicy(
        primary=GrootPolicy(),
        fallback=ScriptedPolicy(POSES_DIR, arm="right"),
    )
    action = policy.predict(Observation(goal="load_workpiece"))
    assert action.arm == "right"
    assert len(action.joint_targets) == 7


def test_fallback_policy_uses_primary_when_available() -> None:
    """FallbackPolicy nutzt die Primary-Policy, wenn diese kein Fehler wirft."""
    policy = FallbackPolicy(
        primary=ScriptedPolicy(POSES_DIR, arm="left"),
        fallback=ScriptedPolicy(POSES_DIR, arm="right"),
    )
    # primary liefert left-Arm-Action
    action = policy.predict(Observation(goal="load_workpiece"))
    assert action.arm == "left"


def test_fallback_policy_reset_does_not_raise() -> None:
    """FallbackPolicy.reset setzt beide Policies ohne Fehler zurück."""
    policy = FallbackPolicy(
        primary=GrootPolicy(),
        fallback=ScriptedPolicy(POSES_DIR),
    )
    policy.reset()  # kein Fehler erwartet


# ---------------------------------------------------------------------------
# Skill mit Policy-Pfad (SkillContext.policy gesetzt)
# ---------------------------------------------------------------------------

def test_load_skill_with_scripted_policy_succeeds(
    plc_env, sim_robot, sim_locomotion
) -> None:
    """LoadWorkpieceSkill läuft erfolgreich durch, wenn policy im SkillContext gesetzt."""
    plc_env.simulator.send_job(JobRequest.LOAD, job_id=10)
    policy = SafeguardedPolicy(ScriptedPolicy(POSES_DIR, arm="right"), _JOINT_LIMITS)
    ctx = SkillContext(
        robot=sim_robot,
        motion=TeachReplayPlanner(sim_robot, POSES_DIR),
        machine=plc_env.machine,
        locomotion=sim_locomotion,
        policy=policy,
    )
    skill = LoadWorkpieceSkill(ctx)
    assert skill.precondition() is True
    assert skill.execute() is True
