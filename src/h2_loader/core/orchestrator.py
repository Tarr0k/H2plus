"""Orchestrator: baut den Ablauf aus Skills und tickt ihn.

Verdrahtet die Skills zu einer Sequenz. Mit installiertem py_trees entsteht ein
echter Behavior Tree (Sequence-Knoten); ohne py_trees greift ein schlanker
Fallback-Runner mit identischer Semantik, damit Dry-Run und Tests ohne
Zusatz-Dependency laufen.
"""

from __future__ import annotations

from ..skills.base import SkillInterface
from ..util.logging import get_logger
from .behavior.skill_behavior import _HAS_PYTREES, make_skill_node
from .safety import SafetyGate

_log = get_logger(__name__)


class Orchestrator:
    """Führt eine geordnete Folge von Skills aus.

    Args:
        skills: Skills in Ausführungsreihenfolge.
        safety: Freigabe-Gate, das vor dem Ticken geprüft wird.
    """

    def __init__(self, skills: list[SkillInterface], safety: SafetyGate | None = None) -> None:
        self._skills = skills
        self._safety = safety or SafetyGate()
        self._nodes = [make_skill_node(s) for s in skills]

    def tick_once(self) -> bool:
        """Tickt die Skill-Sequenz genau einmal durch.

        Returns:
            True, wenn alle Skills erfolgreich durchliefen.
        """
        if not self._safety.is_clear():
            _log.error("Orchestrator: Sicherheitsfreigabe fehlt — Abbruch")
            return False

        _log.info("Orchestrator: Tick start (%d Skills, py_trees=%s)", len(self._skills), _HAS_PYTREES)
        if _HAS_PYTREES:
            return self._tick_pytrees()
        return self._tick_fallback()

    def _tick_fallback(self) -> bool:
        for node in self._nodes:
            if not node.tick_once():
                _log.warning("Orchestrator: Skill '%s' fehlgeschlagen — Sequenz gestoppt", node.name)
                return False
        _log.info("Orchestrator: Sequenz erfolgreich")
        return True

    def _tick_pytrees(self) -> bool:  # pragma: no cover - benötigt py_trees-Installation
        import py_trees

        root = py_trees.composites.Sequence(name="h2_loader", memory=True)
        root.add_children(self._nodes)
        tree = py_trees.trees.BehaviourTree(root)
        tree.tick()
        ok = root.status == py_trees.common.Status.SUCCESS
        _log.info("Orchestrator: BT-Status=%s", root.status)
        return ok
