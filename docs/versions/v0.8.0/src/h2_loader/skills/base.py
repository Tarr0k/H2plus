"""Skill-Interface und gemeinsamer Ausführungskontext.

Jeder Skill implementiert das Tripel ``precondition() -> execute() -> recover()``.
Dieses Tripel bildet sich 1:1 auf Behavior-Tree-Knoten ab (siehe
``core/orchestrator.py``): die Vorbedingung als Guard, ``execute`` als Aktion,
``recover`` als Fehlerpfad.

Der ``SkillContext`` bündelt die Abhängigkeiten, die ein Skill braucht — alle als
Interfaces bzw. Fassaden. So bekommt ein Skill nie einen konkreten Treiber zu sehen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..hal.locomotion.base import LocomotionInterface
from ..hal.robot import Robot
from ..motion.base import MotionPlannerInterface
from ..perception.base import PerceptionInterface
from ..plc.machine_io import MachineIo
from ..policy.base import PolicyInterface


@dataclass
class SkillContext:
    """Abhängigkeiten eines Skills (ausschließlich Interfaces/Fassaden).

    Attributes:
        robot:      HAL-Fassade (Arme + Endeffektoren).
        motion:     Bewegungs-Backend (Replay-Backend heute, ROS2-Backend später).
        machine:    Semantische Maschinen-Fassade über die H2-UDT.
        locomotion: Locomotion-Backend (Laufen zwischen Stationen).
        perception: Optionale Wahrnehmung (im ersten Ausbau meist None).
        policy:     Optionale Manipulations-Policy (ADR-0007); falls gesetzt,
                    wird Arm-Bewegung über Policy statt direkt über motion erzeugt.
    """

    robot: Robot
    motion: MotionPlannerInterface
    machine: MachineIo
    locomotion: LocomotionInterface
    perception: PerceptionInterface | None = field(default=None)
    policy: PolicyInterface | None = field(default=None)


class SkillInterface(ABC):
    """Abstrakter Anwendungs-Skill (precondition/execute/recover)."""

    name: str = "skill"

    def __init__(self, ctx: SkillContext) -> None:
        self.ctx = ctx

    @abstractmethod
    def precondition(self) -> bool:
        """Prüft, ob der Skill jetzt ausgeführt werden darf (Guard)."""

    @abstractmethod
    def execute(self) -> bool:
        """Führt den Skill aus. Returns True bei Erfolg."""

    @abstractmethod
    def recover(self) -> None:
        """Bringt das System nach einem Fehler in einen sicheren Zustand."""
