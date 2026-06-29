"""Skill-Interface und gemeinsamer Ausführungskontext.

Jeder Skill implementiert das Tripel ``precondition() -> execute() -> recover()``.
Dieses Tripel bildet sich 1:1 auf Behavior-Tree-Knoten ab (siehe
``core/orchestrator.py``): die Vorbedingung als Guard, ``execute`` als Aktion,
``recover`` als Fehlerpfad.

Der ``SkillContext`` bündelt die Abhängigkeiten, die ein Skill braucht — alle als
Interfaces. So bekommt ein Skill nie einen konkreten Treiber zu sehen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..hal.robot import Robot
from ..motion.base import MotionPlannerInterface
from ..perception.base import PerceptionInterface
from ..plc.base import PlcInterface


@dataclass
class SkillContext:
    """Abhängigkeiten eines Skills (ausschließlich Interfaces/Fassaden).

    Attributes:
        robot: HAL-Fassade (Arme + Endeffektoren).
        motion: Bewegungs-Backend (Replay-Backend heute, ROS2-Backend später).
        plc: Maschinen-SPS für den Handshake.
        perception: optionale Wahrnehmung (im ersten Ausbau meist None).
    """

    robot: Robot
    motion: MotionPlannerInterface
    plc: PlcInterface
    perception: PerceptionInterface | None = None


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
