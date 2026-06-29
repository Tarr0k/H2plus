"""Skill: Werkstück in die Maschine laden.

Mehrstufige Sequenz (Stub-Aufrufe + Logging) mit Locomotion-Ebene, die den
typischen Handshake mit der Maschinen-SPS abbildet:

    Vorbedingung:  Tür offen UND Spannvorrichtung frei
    Ablauf:        laufe zu part_storage -> Arm zur Aufnahme -> greifen
                   -> laufe zu machine -> warte auf Tür offen
                   -> Arm zur Spannvorrichtung -> einlegen (loslassen)
                   -> ROBOT_DONE an SPS melden
    Recover:       Greifer öffnen, laufe zu home

Es findet keine echte Bewegung statt — die Stubs der unteren Schichten loggen
nur die Schritte.
"""

from __future__ import annotations

from ..util.logging import get_logger
from ..plc.signals import Signal
from .base import SkillInterface

_log = get_logger(__name__)

# Verwendeter Arm und angelernte Posen (Posen liegen in config/poses/).
ARM = "right"
PICK_POSE = "load_workpiece"          # Aufnahmeposition des Rohteils
PLACE_POSE = "unload_workpiece"       # Einlegeposition in der Spannvorrichtung


class LoadWorkpieceSkill(SkillInterface):
    """Lädt ein Werkstück von der Aufnahme in die Spannvorrichtung."""

    name = "load_workpiece"

    def precondition(self) -> bool:
        door = self.ctx.plc.read_signal(Signal.DOOR_OPEN)
        free = self.ctx.plc.read_signal(Signal.FIXTURE_FREE)
        _log.info("precondition: DOOR_OPEN=%s FIXTURE_FREE=%s", door, free)
        return door and free

    def execute(self) -> bool:
        gripper = self.ctx.robot.arm(ARM).end_effector

        _log.info("execute: laufe zu Teilelager (part_storage)")
        self.ctx.locomotion.move_to("part_storage")

        _log.info("execute: zur Aufnahme fahren -> greifen")
        self.ctx.motion.move_to(ARM, PICK_POSE)
        gripper.grasp()

        _log.info("execute: laufe zur Maschine (machine)")
        self.ctx.locomotion.move_to("machine")

        _log.info("execute: warte auf Tür offen")
        self.ctx.plc.wait_for(Signal.DOOR_OPEN, True)

        _log.info("execute: zur Spannvorrichtung fahren -> einlegen")
        self.ctx.motion.move_to(ARM, PLACE_POSE)
        gripper.release()

        _log.info("execute: ROBOT_DONE an SPS melden")
        self.ctx.plc.write_signal(Signal.ROBOT_DONE, True)
        return True

    def recover(self) -> None:
        _log.warning("recover: Greifer öffnen, laufe zu home")
        self.ctx.robot.arm(ARM).end_effector.release()
        self.ctx.locomotion.move_to("home")
