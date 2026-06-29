"""Interface für Endeffektoren ("Hände").

Skills rufen ausschließlich ``grasp()``/``release()``/``is_holding()``. Welcher
konkrete Endeffektor dahintersteckt — heute der pneumatische Backengreifer,
später eine Mehrfingerhand oder ein Schrauber für den Induktorwechsel — ist für
den Skill-Code unsichtbar. Das ist der zentrale Austauschpunkt für Werkzeuge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EndEffectorInterface(ABC):
    """Abstrakter Endeffektor: greifen, loslassen, Haltezustand abfragen."""

    @abstractmethod
    def grasp(self) -> None:
        """Schließt den Endeffektor / greift das Werkstück."""

    @abstractmethod
    def release(self) -> None:
        """Öffnet den Endeffektor / lässt das Werkstück los."""

    @abstractmethod
    def is_holding(self) -> bool:
        """True, wenn (laut Sensorik/Annahme) aktuell ein Werkstück gehalten wird."""
