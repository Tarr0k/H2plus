"""Akku-/Pneumatik-Schrauber als Endeffektor (Stub).

Realer Einsatz: Ein pneumatischer oder akkubetriebener Schrauber, der per
Tool-Changer (z. B. ATI QC) an einem Roboterarm befestigt wird.  Hier
Stub-Implementierung — alle Aktionen werden nur geloggt, kein echtes
Drehmoment oder Motorstrom.

Verwendung: Induktorwechsel (2 Schrauben lösen/anziehen).  Weil ein
1-Zylinder-Backengreifer keine Schrauben betätigen kann, muss vor dem
Schraubvorgang ein Werkzeugwechsel stattfinden (siehe ToolChanger).
"""

from __future__ import annotations

from ...util.logging import get_logger
from .base import EndEffectorInterface

_log = get_logger(__name__)


class ScrewdriverEndEffector(EndEffectorInterface):
    """Akku-/Pneumatik-Schrauber (Stub).

    Implementiert das ``EndEffectorInterface`` (grasp/release/is_holding),
    damit er transparent über den Tool-Changer eingesetzt werden kann.
    Zusätzlich stehen ``loosen()`` und ``tighten()`` für das eigentliche
    Schrauben zur Verfügung.

    Args:
        label: Optionale Bezeichnung für Logging (z. B. ``"screwdriver_right"``).
    """

    def __init__(self, label: str = "screwdriver") -> None:
        self._label = label
        self._engaged = False  # Bit am Schraubenkopf eingekuppelt?

    # ------------------------------------------------------------------
    # EndEffectorInterface
    # ------------------------------------------------------------------

    def grasp(self) -> None:
        """Setzt den Schrauberbit am Schraubenkopf an (einkuppeln)."""
        _log.info("%s: grasp — Bit am Schraubenkopf angesetzt (eingekuppelt)", self._label)
        self._engaged = True

    def release(self) -> None:
        """Zieht den Schrauberbit vom Schraubenkopf zurück."""
        _log.info("%s: release — Bit zurückgezogen", self._label)
        self._engaged = False

    def is_holding(self) -> bool:
        """True, wenn der Bit aktuell am Schraubenkopf eingekuppelt ist."""
        return self._engaged

    # ------------------------------------------------------------------
    # Schrauber-spezifische Methoden
    # ------------------------------------------------------------------

    def loosen(self, turns: float = 0.0) -> None:
        """Löst eine Schraube (linksherum drehen).

        Args:
            turns: Anzahl der Umdrehungen (0.0 = bis Anschlag/Stub).
        """
        _log.info(
            "%s: loosen — Schraube lösen (turns=%.2f) [Stub]",
            self._label,
            turns,
        )

    def tighten(self, turns: float = 0.0) -> None:
        """Zieht eine Schraube an (rechtsherum drehen).

        Args:
            turns: Anzahl der Umdrehungen (0.0 = bis Anzugsmoment/Stub).
        """
        _log.info(
            "%s: tighten — Schraube anziehen (turns=%.2f) [Stub]",
            self._label,
            turns,
        )
