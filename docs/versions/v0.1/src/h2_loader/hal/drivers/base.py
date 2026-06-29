"""Treiber-Interface für den Roboter-Lowlevel-Zugriff.

Ein ``RobotDriverInterface`` kapselt die Verbindung zur Roboter-Hardware bzw.
zur Simulation. MuJoCo-Sim und reale HW nutzen laut Projektdoku dieselbe
DDS-Schnittstelle — deshalb lässt sich per ``config/robot.yaml`` zwischen beiden
umschalten (Sim-to-Real), ohne Aufrufer zu ändern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class JointState:
    """Momentaufnahme der Gelenke beider Arme.

    Attributes:
        positions: Mapping Armseite ("left"/"right") -> Liste der 7 Gelenkwinkel [rad].
        timestamp: optionaler Zeitstempel der Messung [s]; vom Aufrufer gesetzt.
    """

    positions: dict[str, list[float]] = field(default_factory=dict)
    timestamp: float | None = None


class RobotDriverInterface(ABC):
    """Abstrakter Lowlevel-Treiber: Verbindung, Soll-Gelenke senden, Ist-Zustand lesen."""

    @abstractmethod
    def connect(self) -> None:
        """Baut die Verbindung zum Roboter/zur Sim auf."""

    @abstractmethod
    def disconnect(self) -> None:
        """Trennt die Verbindung sauber."""

    @abstractmethod
    def send_joints(self, arm: str, positions: list[float]) -> None:
        """Sendet Soll-Gelenkwinkel [rad] für den angegebenen Arm ("left"/"right")."""

    @abstractmethod
    def read_state(self) -> JointState:
        """Liest den aktuellen Gelenkzustand beider Arme."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """True, wenn die Verbindung steht."""
