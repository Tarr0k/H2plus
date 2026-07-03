"""Tests für die Gelenkindex-Konstanten des H2 (EDU)."""

from __future__ import annotations

from h2_loader.hal.h2_joint_index import H2JointIndex

# Die 29 kanonischen Gelenknamen (ohne Parallelmechanismus-Aliase wie LeftAnkleB).
_CANONICAL_29 = [
    "LeftHipPitch", "LeftHipRoll", "LeftHipYaw", "LeftKnee", "LeftAnklePitch", "LeftAnkleRoll",
    "RightHipPitch", "RightHipRoll", "RightHipYaw", "RightKnee", "RightAnklePitch", "RightAnkleRoll",
    "WaistYaw", "WaistRoll", "WaistPitch",
    "LeftShoulderPitch", "LeftShoulderRoll", "LeftShoulderYaw", "LeftElbow",
    "LeftWristRoll", "LeftWristPitch", "LeftWristYaw",
    "RightShoulderPitch", "RightShoulderRoll", "RightShoulderYaw", "RightElbow",
    "RightWristRoll", "RightWristPitch", "RightWristYaw",
]


def test_29_kanonische_indizes_eindeutig_0_bis_28() -> None:
    """Die 29 kanonischen Gelenknamen decken lückenlos und eindeutig 0-28 ab."""
    indices = [getattr(H2JointIndex, name) for name in _CANONICAL_29]
    assert len(indices) == 29
    assert sorted(indices) == list(range(29))


def test_parallelmechanismus_aliase_zeigen_auf_denselben_index() -> None:
    """LeftAnkleB/LeftAnkleA (bzw. rechts) sind Aliase der Pitch/Roll-Achsen."""
    assert H2JointIndex.LeftAnkleB == H2JointIndex.LeftAnklePitch
    assert H2JointIndex.LeftAnkleA == H2JointIndex.LeftAnkleRoll
    assert H2JointIndex.RightAnkleB == H2JointIndex.RightAnklePitch
    assert H2JointIndex.RightAnkleA == H2JointIndex.RightAnkleRoll


def test_left_arm_tuple() -> None:
    assert H2JointIndex.LEFT_ARM == (15, 16, 17, 18, 19, 20, 21)


def test_right_arm_tuple() -> None:
    assert H2JointIndex.RIGHT_ARM == (22, 23, 24, 25, 26, 27, 28)


def test_arm_tuples_disjunkt_und_je_7_lang() -> None:
    assert len(H2JointIndex.LEFT_ARM) == 7
    assert len(H2JointIndex.RIGHT_ARM) == 7
    assert set(H2JointIndex.LEFT_ARM).isdisjoint(H2JointIndex.RIGHT_ARM)
