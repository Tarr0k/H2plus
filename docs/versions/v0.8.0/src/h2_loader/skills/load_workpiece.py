"""Skill: Werkstück in die Maschine laden.

Mehrstufige Sequenz (Stub-Aufrufe + Logging) mit Locomotion-Ebene, die den
typischen Handshake mit der Maschinen-SPS abbildet:

    Vorbedingung:  Tür offen UND Spannvorrichtung frei
    Ablauf:        laufe zu part_storage -> Arm zur Aufnahme -> greifen
                   -> laufe zu machine -> warte auf Tür offen
                   -> Arm zur Spannvorrichtung -> einlegen (loslassen)
                   -> Spannvorrichtung schließen anfordern -> warten
    Recover:       Greifer öffnen, laufe zu home

Es findet keine echte Bewegung statt — die Stubs der unteren Schichten loggen
nur die Schritte.
"""

from __future__ import annotations

from ..policy.base import Observation
from ..util.logging import get_logger
from .base import SkillInterface

_log = get_logger(__name__)

# Verwendeter Arm und angelernte Posen (Posen liegen in config/poses/).
ARM = "right"
PICK_POSE = "load_workpiece"          # Aufnahmeposition des Rohteils
PLACE_POSE = "unload_workpiece"       # Einlegeposition in der Spannvorrichtung


class LoadWorkpieceSkill(SkillInterface):
    """Lädt ein Werkstück von der Aufnahme in die Spannvorrichtung."""

    name = "load_workpiece"

    def _reach(self, arm: str, pose: str) -> None:
        """Fährt einen Arm auf eine Pose — über Policy oder direkt über motion.

        Falls ``ctx.policy`` gesetzt ist, erzeugt die Policy die Gelenkwinkel
        aus der Ziel-Pose (ADR-0007); sonst wird ``ctx.motion.move_to`` genutzt.

        Args:
            arm:  Armseite ("left"/"right").
            pose: Name der angelernten Ziel-Pose.
        """
        if self.ctx.policy is not None:
            action = self.ctx.policy.predict(Observation(goal=pose))
            self.ctx.robot.arm(action.arm).move_joints(action.joint_targets)
        else:
            self.ctx.motion.move_to(arm, pose)

    def precondition(self) -> bool:
        door = self.ctx.machine.door_open()
        free = self.ctx.machine.fixture_free()
        _log.info("precondition: door_open=%s fixture_free=%s", door, free)
        return door and free

    def execute(self) -> bool:
        gripper = self.ctx.robot.arm(ARM).end_effector

        _log.info("execute: laufe zu Teilelager (part_storage)")
        self.ctx.locomotion.move_to("part_storage")

        _log.info("execute: zur Aufnahme fahren -> greifen")
        self._reach(ARM, PICK_POSE)
        gripper.grasp()
        self.ctx.machine.set_gripper_holds(True)

        _log.info("execute: laufe zur Maschine (machine)")
        self.ctx.locomotion.move_to("machine")

        _log.info("execute: warte auf Tür offen")
        self.ctx.machine.wait_door_open()

        _log.info("execute: zur Spannvorrichtung fahren -> einlegen")
        self._reach(ARM, PLACE_POSE)
        gripper.release()
        self.ctx.machine.set_gripper_holds(False)

        _log.info("execute: Spannvorrichtung schließen anfordern")
        self.ctx.machine.request_close_clamp()

        _log.info("execute: warte auf Spannvorrichtung geschlossen")
        self.ctx.machine.wait_clamp_closed()

        return True

    def recover(self) -> None:
        _log.warning("recover: Greifer öffnen, laufe zu home")
        self.ctx.robot.arm(ARM).end_effector.release()
        self.ctx.locomotion.move_to("home")
