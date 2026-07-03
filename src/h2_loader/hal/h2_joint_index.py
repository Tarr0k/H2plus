"""Gelenkindizes des Unitree H2 (EDU) — reine Konstanten, keine SDK-Abhängigkeit.

Der H2 hat 29 steuerbare Gelenke (Index 0–28), adressiert über die
``unitree_hg``-IDL (``LowCmd_``/``LowState_``, Felder ``motor_cmd``/``motor_state``).
Reihenfolge und Namen sind an ``unitree_h2_dokumentation.md`` und
``docs/sdk_reference.md`` angelehnt:

    0–11:  Beine (je 6 Achsen: Hip Pitch/Roll/Yaw, Knee, Ankle Pitch/Roll)
    12–14: Taille (WaistYaw, WaistRoll, WaistPitch)
    15–21: linker Arm (ShoulderPitch/Roll/Yaw, Elbow, WristRoll/Pitch/Yaw)
    22–28: rechter Arm (analog links)

Knöchel und Taille nutzen mechanisch einen Parallelmechanismus mit zwei
Steuermodi (PR/AB) — daher die Doppelbenennung der Knöchelachsen
(``LeftAnklePitch``/``LeftAnkleB``, ``LeftAnkleRoll``/``LeftAnkleA``; analog
rechts). Beide Namen adressieren denselben Index.

Kopf-Gelenke (Indizes 29/30) existieren mechanisch, sind für den Lader aber
nicht relevant und deshalb NICHT Teil dieses Index.
"""

from __future__ import annotations


class H2JointIndex:
    """Namentliche Gelenkindizes 0–28 des H2 (EDU) als Klassenkonstanten."""

    # Linkes Bein (0-5)
    LeftHipPitch = 0
    LeftHipRoll = 1
    LeftHipYaw = 2
    LeftKnee = 3
    LeftAnklePitch = 4
    LeftAnkleB = 4  # Parallelmechanismus-Alias, siehe Modul-Docstring
    LeftAnkleRoll = 5
    LeftAnkleA = 5

    # Rechtes Bein (6-11)
    RightHipPitch = 6
    RightHipRoll = 7
    RightHipYaw = 8
    RightKnee = 9
    RightAnklePitch = 10
    RightAnkleB = 10
    RightAnkleRoll = 11
    RightAnkleA = 11

    # Taille (12-14)
    WaistYaw = 12
    WaistRoll = 13
    WaistPitch = 14

    # Linker Arm (15-21)
    LeftShoulderPitch = 15
    LeftShoulderRoll = 16
    LeftShoulderYaw = 17
    LeftElbow = 18
    LeftWristRoll = 19
    LeftWristPitch = 20
    LeftWristYaw = 21

    # Rechter Arm (22-28)
    RightShoulderPitch = 22
    RightShoulderRoll = 23
    RightShoulderYaw = 24
    RightElbow = 25
    RightWristRoll = 26
    RightWristPitch = 27
    RightWristYaw = 28

    # Bequeme Gruppen für Arm-Ansteuerung (Reihenfolge = Arm.DOF-Reihenfolge)
    LEFT_ARM: tuple[int, ...] = (
        LeftShoulderPitch,
        LeftShoulderRoll,
        LeftShoulderYaw,
        LeftElbow,
        LeftWristRoll,
        LeftWristPitch,
        LeftWristYaw,
    )
    RIGHT_ARM: tuple[int, ...] = (
        RightShoulderPitch,
        RightShoulderRoll,
        RightShoulderYaw,
        RightElbow,
        RightWristRoll,
        RightWristPitch,
        RightWristYaw,
    )
