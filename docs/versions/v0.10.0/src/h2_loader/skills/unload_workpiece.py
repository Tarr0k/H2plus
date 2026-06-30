"""Skill: Werkstück aus der Maschine entnehmen.

Mehrstufiges Spiegelbild zu ``load_workpiece`` mit Locomotion-Ebene:

    Vorbedingung:  Bearbeitung fertig (cycle_done) UND Tür offen
    Ablauf:        laufe zu machine -> Spannvorrichtung öffnen anfordern
                   -> warte auf Spannvorrichtung offen
                   -> Arm zur Spannvorrichtung -> greifen
                   -> laufe zu dropoff_box -> Arm zur Ablage -> ablegen
    Recover:       Greifer öffnen, laufe zu home
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import SkillInterface

_log = get_logger(__name__)

ARM = "right"
PICK_POSE = "unload_workpiece"        # Entnahme aus der Spannvorrichtung
PLACE_POSE = "load_workpiece"         # Ablage des Fertigteils


class UnloadWorkpieceSkill(SkillInterface):
    """Entnimmt ein fertig bearbeitetes Werkstück und legt es ab."""

    name = "unload_workpiece"

    def precondition(self) -> bool:
        done = self.ctx.machine.cycle_done()
        door = self.ctx.machine.door_open()
        _log.info("precondition: cycle_done=%s door_open=%s", done, door)
        return done and door

    def execute(self) -> bool:
        gripper = self.ctx.robot.arm(ARM).end_effector

        _log.info("execute: laufe zur Maschine (machine)")
        self.ctx.locomotion.move_to("machine")

        _log.info("execute: Spannvorrichtung öffnen anfordern")
        self.ctx.machine.request_open_clamp()

        _log.info("execute: warte auf Spannvorrichtung offen")
        self.ctx.machine.wait_clamp_open()

        _log.info("execute: zur Spannvorrichtung fahren -> greifen -> entnehmen")
        self._reach(ARM, PICK_POSE)
        gripper.grasp()
        self.ctx.machine.set_gripper_holds(True)

        _log.info("execute: laufe zur Fertigteil-Kiste (dropoff_box)")
        self.ctx.locomotion.move_to("dropoff_box")

        _log.info("execute: zur Ablage fahren -> ablegen")
        self._reach(ARM, PLACE_POSE)
        gripper.release()
        self.ctx.machine.set_gripper_holds(False)

        return True

    def recover(self) -> None:
        _log.warning("recover: Greifer öffnen, laufe zu home")
        self.ctx.robot.arm(ARM).end_effector.release()
        self.ctx.locomotion.move_to("home")
