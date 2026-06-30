"""Werkzeugwechsler (Tool-Changer) — Stub.

Real: ein automatischer Tool-Changer (z. B. ATI QC) an einer Dock-Station,
der einen Endeffektor elektrisch/pneumatisch verriegelt.  Hier direkter
Tausch + Logging ohne physische Ansteuerung.

Typischer Einsatz: Wechsel zwischen Pneumatikgreifer und Schrauber für den
Induktorwechsel (``ChangeInductorSkill``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..util.logging import get_logger

if TYPE_CHECKING:
    from .end_effector.base import EndEffectorInterface
    from .robot import Robot

_log = get_logger(__name__)


class ToolChanger:
    """Verwaltet den Werkzeugwechsel an einem oder mehreren Roboterarmen.

    Args:
        robot:        Roboter-Fassade, über die ``arm(side).set_end_effector()``
                      aufgerufen wird.
        tools:        Mapping Tool-Name → Endeffektor-Instanz.
                      Beispiel: ``{"gripper": PneumaticGripper(...), "screwdriver": ScrewdriverEndEffector(...)}``.
        default_tool: Name des Tools, das beim Start als aktives Werkzeug
                      pro Arm gesetzt wird.  Muss in ``tools`` vorhanden sein.

    Raises:
        KeyError: Wenn ``default_tool`` nicht in ``tools`` enthalten ist.
    """

    def __init__(
        self,
        robot: Robot,
        tools: dict[str, EndEffectorInterface],
        default_tool: str = "gripper",
    ) -> None:
        if default_tool not in tools:
            raise KeyError(
                f"ToolChanger: default_tool {default_tool!r} nicht in tools "
                f"(verfügbar: {sorted(tools)})"
            )
        self._robot = robot
        self._tools = tools
        # Startbelegung: jeder Arm trägt das Standard-Werkzeug
        self._current: dict[str, str] = {
            side: default_tool for side in robot.sides
        }

    def equip(self, arm: str, tool: str) -> None:
        """Wechselt den Endeffektor eines Arms auf das gewünschte Tool.

        Args:
            arm:  Armseite ("left"/"right").
            tool: Name des neuen Tools (muss in ``tools`` vorhanden sein).

        Raises:
            KeyError: Wenn ``tool`` nicht in ``tools`` registriert ist.
        """
        if tool not in self._tools:
            raise KeyError(
                f"ToolChanger.equip: unbekanntes Tool {tool!r} "
                f"(verfügbar: {sorted(self._tools)})"
            )
        current = self._current.get(arm, "")
        if current == tool:
            _log.info(
                "ToolChanger.equip: Arm[%s] trägt bereits %r — kein Wechsel nötig",
                arm,
                tool,
            )
            return
        _log.info(
            "ToolChanger.equip: Werkzeugwechsel Arm[%s] %r -> %r",
            arm,
            current,
            tool,
        )
        self._robot.arm(arm).set_end_effector(self._tools[tool])
        self._current[arm] = tool

    def current_tool(self, arm: str) -> str:
        """Gibt den Namen des aktuell montierten Tools zurück.

        Args:
            arm: Armseite ("left"/"right").

        Returns:
            Tool-Name oder leerer String, wenn der Arm unbekannt ist.
        """
        return self._current.get(arm, "")
