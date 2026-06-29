"""Adapter: ein ``SkillInterface`` als py_trees-Behaviour.

Bildet das Skill-Tripel auf einen Behavior-Tree-Knoten ab:

    initialise() -> precondition()  (FAILURE, wenn nicht erfüllt)
    update()     -> execute()       (SUCCESS/FAILURE)
    on FAILURE   -> recover()

py_trees ist eine Kern-Abhängigkeit (siehe pyproject). Der Import ist dennoch
defensiv gekapselt, damit das Paket auch ohne installiertes py_trees importier-
und (über den Fallback-Runner im Orchestrator) testbar bleibt.
"""

from __future__ import annotations

from ...skills.base import SkillInterface
from ...util.logging import get_logger

_log = get_logger(__name__)

try:  # pragma: no cover - abhängig von der Umgebung
    import py_trees

    _HAS_PYTREES = True
except ImportError:  # pragma: no cover
    py_trees = None  # type: ignore[assignment]
    _HAS_PYTREES = False


if _HAS_PYTREES:

    class SkillBehaviour(py_trees.behaviour.Behaviour):  # type: ignore[misc]
        """py_trees-Behaviour, das einen Skill kapselt."""

        def __init__(self, skill: SkillInterface) -> None:
            super().__init__(name=skill.name)
            self._skill = skill

        def update(self) -> "py_trees.common.Status":
            if not self._skill.precondition():
                _log.info("Skill[%s]: precondition nicht erfüllt -> FAILURE", self._skill.name)
                return py_trees.common.Status.FAILURE
            try:
                ok = self._skill.execute()
            except Exception:  # noqa: BLE001 - im BT zu FAILURE degradieren
                _log.exception("Skill[%s]: execute warf Exception -> recover", self._skill.name)
                self._skill.recover()
                return py_trees.common.Status.FAILURE
            if ok:
                return py_trees.common.Status.SUCCESS
            self._skill.recover()
            return py_trees.common.Status.FAILURE

else:

    class SkillBehaviour:  # type: ignore[no-redef]
        """Fallback-Knoten ohne py_trees (gleiche Semantik, minimal)."""

        def __init__(self, skill: SkillInterface) -> None:
            self.name = skill.name
            self._skill = skill

        def tick_once(self) -> bool:
            if not self._skill.precondition():
                _log.info("Skill[%s]: precondition nicht erfüllt", self._skill.name)
                return False
            try:
                ok = self._skill.execute()
            except Exception:  # noqa: BLE001
                _log.exception("Skill[%s]: execute warf Exception -> recover", self._skill.name)
                self._skill.recover()
                return False
            if not ok:
                self._skill.recover()
            return ok


def make_skill_node(skill: SkillInterface) -> SkillBehaviour:
    """Erzeugt den passenden Behaviour-Knoten für einen Skill."""
    return SkillBehaviour(skill)
