"""Skill: Induktor wechseln (v0.10.0).

Der Induktor sitzt in einer Führung und ist mit **2 Schrauben** befestigt.
Ein 1-Zylinder-Pneumatikgreifer kann keine Schrauben lösen — dieser Skill
setzt daher einen ``ToolChanger`` voraus, der den Greifer gegen einen
``ScrewdriverEndEffector`` tauscht und nach dem Schraubvorgang wieder zurück.

Hinweis: Alternativ wäre ein zweiarmiger Ansatz möglich (ein Arm führt den
Schrauber, der andere Arm hält/positioniert den Induktor).  Hier wird der
einarmige Werkzeugwechsel (Greifer ↔ Schrauber) modelliert, da er mit der
aktuellen Hardware-Konfiguration (ein aktiver Arm für Feinmanipulation)
robuster ist.

Ablauf (einarmig):
    1. Zur Maschine laufen.
    2. Tür sicherstellen (request_open_door + wait_door_open).
    3. Werkzeug: Greifer → Schrauber.
    4. Schrauben lösen (2×).
    5. Werkzeug: Schrauber → Greifer.
    6. Alten Induktor entnehmen.
    7. Zum Induktor-Regal, alten ablegen, neuen aufnehmen, zurück zur Maschine.
    8. Neuen Induktor in Führung einsetzen.
    9. Werkzeug: Greifer → Schrauber.
    10. Schrauben anziehen (2×).
    11. Werkzeug: Schrauber → Greifer (Standardzustand wiederherstellen).
"""

from __future__ import annotations

from ..hal.end_effector.screwdriver import ScrewdriverEndEffector
from ..util.logging import get_logger
from .base import SkillInterface

_log = get_logger(__name__)

ARM = "right"

# Angelernte Posen (liegen in config/poses/)
POSE_SCREW_1  = "inductor_screw_1"
POSE_SCREW_2  = "inductor_screw_2"
POSE_PICK     = "inductor_pick"
POSE_PLACE    = "inductor_place"


class ChangeInductorSkill(SkillInterface):
    """Wechselt den Induktor (2 Schrauben) mit einarmigem Werkzeugwechsel."""

    name = "change_inductor"

    def precondition(self) -> bool:
        """Prüft alle Voraussetzungen für den Induktorwechsel.

        Bedingungen:
        - ``tool_changer`` muss im Kontext gesetzt sein.
        - Maschine muss betriebsbereit sein (``machine_ready``).
        - Tür muss geöffnet sein (``door_open``).
        - Kein laufender Bearbeitungszyklus (``not cycle_running``).
        """
        if self.ctx.tool_changer is None:
            _log.warning(
                "change_inductor.precondition: kein ToolChanger im Kontext — False"
            )
            return False
        ready   = self.ctx.machine.machine_ready()
        door    = self.ctx.machine.door_open()
        no_run  = not self.ctx.machine.cycle_running()
        _log.info(
            "change_inductor.precondition: machine_ready=%s door_open=%s cycle_running=%s",
            ready,
            door,
            not no_run,
        )
        return ready and door and no_run

    def execute(self) -> bool:
        """Führt den vollständigen Induktorwechsel durch.

        Returns:
            True bei erfolgreichem Abschluss.
        """
        tc      = self.ctx.tool_changer
        machine = self.ctx.machine
        loco    = self.ctx.locomotion

        # Schritt 1: zur Maschine laufen
        machine.set_current_step(1)
        _log.info("change_inductor.execute Schritt 1: laufe zur Maschine")
        loco.move_to("machine")

        # Schritt 2: Tür sicherstellen
        machine.set_current_step(2)
        _log.info("change_inductor.execute Schritt 2: Tür öffnen sicherstellen")
        machine.request_open_door()
        machine.wait_door_open()

        # Schritt 3: Werkzeug → Schrauber
        machine.set_current_step(3)
        _log.info("change_inductor.execute Schritt 3: Werkzeugwechsel -> Schrauber")
        tc.equip(ARM, "screwdriver")
        screwdriver = self.ctx.robot.arm(ARM).end_effector
        if not isinstance(screwdriver, ScrewdriverEndEffector):
            _log.error(
                "change_inductor.execute: Endeffektor nach equip('screwdriver') "
                "ist kein ScrewdriverEndEffector (ist: %s) — Abbruch",
                type(screwdriver).__name__,
            )
            return False

        # Schritt 4: 2 Schrauben lösen
        machine.set_current_step(4)
        _log.info("change_inductor.execute Schritt 4a: zur Schraube 1 fahren -> lösen")
        self._reach(ARM, POSE_SCREW_1)
        screwdriver.loosen()

        _log.info("change_inductor.execute Schritt 4b: zur Schraube 2 fahren -> lösen")
        self._reach(ARM, POSE_SCREW_2)
        screwdriver.loosen()

        # Schritt 5: Werkzeug → Greifer
        machine.set_current_step(5)
        _log.info("change_inductor.execute Schritt 5: Werkzeugwechsel -> Greifer")
        tc.equip(ARM, "gripper")
        gripper = self.ctx.robot.arm(ARM).end_effector

        # Schritt 6: alten Induktor entnehmen
        machine.set_current_step(6)
        _log.info("change_inductor.execute Schritt 6: alten Induktor entnehmen")
        self._reach(ARM, POSE_PICK)
        gripper.grasp()
        machine.set_gripper_holds(True)

        # Schritt 7: Regal — alten ablegen, neuen aufnehmen
        machine.set_current_step(7)
        _log.info("change_inductor.execute Schritt 7: laufe zu Induktor-Regal")
        loco.move_to("inductor_shelf")

        _log.info("change_inductor.execute Schritt 7a: alten Induktor ablegen")
        gripper.release()
        machine.set_gripper_holds(False)

        _log.info("change_inductor.execute Schritt 7b: neuen Induktor aufnehmen")
        gripper.grasp()
        machine.set_gripper_holds(True)

        _log.info("change_inductor.execute Schritt 7c: laufe zurück zur Maschine")
        loco.move_to("machine")

        # Schritt 8: neuen Induktor in Führung einsetzen
        machine.set_current_step(8)
        _log.info("change_inductor.execute Schritt 8: neuen Induktor in Führung einsetzen")
        self._reach(ARM, POSE_PLACE)
        gripper.release()
        machine.set_gripper_holds(False)

        # Schritt 9: Werkzeug → Schrauber, 2 Schrauben anziehen
        machine.set_current_step(9)
        _log.info("change_inductor.execute Schritt 9: Werkzeugwechsel -> Schrauber")
        tc.equip(ARM, "screwdriver")
        screwdriver = self.ctx.robot.arm(ARM).end_effector
        if not isinstance(screwdriver, ScrewdriverEndEffector):
            _log.error(
                "change_inductor.execute: Endeffektor nach zweitem equip('screwdriver') "
                "ist kein ScrewdriverEndEffector (ist: %s) — Abbruch",
                type(screwdriver).__name__,
            )
            return False

        _log.info("change_inductor.execute Schritt 9a: zur Schraube 1 -> anziehen")
        self._reach(ARM, POSE_SCREW_1)
        screwdriver.tighten()

        _log.info("change_inductor.execute Schritt 9b: zur Schraube 2 -> anziehen")
        self._reach(ARM, POSE_SCREW_2)
        screwdriver.tighten()

        # Schritt 10: Standardwerkzeug wiederherstellen (Greifer)
        machine.set_current_step(10)
        _log.info("change_inductor.execute Schritt 10: Werkzeugwechsel -> Greifer (Standardzustand)")
        tc.equip(ARM, "gripper")

        _log.info("change_inductor.execute: Induktorwechsel abgeschlossen")
        return True

    def recover(self) -> None:
        """Sicherer Zustand nach Fehler: Greifer montieren + Heimfahrt."""
        _log.warning("change_inductor.recover: Greifer montieren + laufe zu home")
        if self.ctx.tool_changer is not None:
            self.ctx.tool_changer.equip(ARM, "gripper")
        self.ctx.robot.arm(ARM).end_effector.release()
        self.ctx.locomotion.move_to("home")
