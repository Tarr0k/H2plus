"""Skill: Werkstück aus der Maschine entnehmen.

Spiegelbild zu ``load_workpiece``:

    Vorbedingung:  Bearbeitung fertig (CYCLE_OK) UND Tür offen
    Ablauf:        zur Spannvorrichtung fahren -> greifen -> entnehmen
                   -> zur Ablage fahren -> ablegen -> ROBOT_DONE an SPS
    Recover:       Greifer öffnen
"""

from __future__ import annotations

from ..util.logging import get_logger
from ..plc.signals import Signal
from .base import SkillInterface

_log = get_logger(__name__)

ARM = "right"
PICK_POSE = "unload_workpiece"        # Entnahme aus der Spannvorrichtung
PLACE_POSE = "load_workpiece"         # Ablage des Fertigteils


class UnloadWorkpieceSkill(SkillInterface):
    """Entnimmt ein fertig bearbeitetes Werkstück und legt es ab."""

    name = "unload_workpiece"

    def precondition(self) -> bool:
        done = self.ctx.plc.read_signal(Signal.CYCLE_OK)
        door = self.ctx.plc.read_signal(Signal.DOOR_OPEN)
        _log.info("precondition: CYCLE_OK=%s DOOR_OPEN=%s", done, door)
        return done and door

    def execute(self) -> bool:
        gripper = self.ctx.robot.arm(ARM).end_effector
        _log.info("execute: zur Spannvorrichtung fahren -> greifen -> entnehmen")
        self.ctx.motion.move_to(ARM, PICK_POSE)
        gripper.grasp()

        _log.info("execute: zur Ablage fahren -> ablegen")
        self.ctx.motion.move_to(ARM, PLACE_POSE)
        gripper.release()

        _log.info("execute: ROBOT_DONE an SPS melden")
        self.ctx.plc.write_signal(Signal.ROBOT_DONE, True)
        return True

    def recover(self) -> None:
        _log.warning("recover: Greifer öffnen")
        self.ctx.robot.arm(ARM).end_effector.release()
