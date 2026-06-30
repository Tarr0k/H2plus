"""Lokalisierungs-Interface und In-Memory-Stub für den H2-Navigationregler.

Auf dem Zielsystem liefert LiDAR-Odometrie (``unilidar_sdk2`` +
``point_lio_unilidar``) die Roboterpose in Weltkoordinaten. Hier wird die
Schnittstelle definiert und ein kinematischer Simulationsstub bereitgestellt,
der Geschwindigkeitsbefehle integriert.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def wrap_angle(a: float) -> float:
    """Normalisiert einen Winkel auf den Bereich (-pi, pi].

    Args:
        a: Eingabewinkel in Radiant.

    Returns:
        Äquivalenter Winkel im Bereich (-pi, pi].
    """
    a = math.fmod(a + math.pi, 2 * math.pi)
    if a <= 0:
        a += 2 * math.pi
    return a - math.pi


@dataclass
class Pose2D:
    """Pose des Roboters in der Zellen-Weltkoordinaten.

    Attributes:
        x:     X-Position [m].
        y:     Y-Position [m].
        theta: Orientierung [rad], normalisiert auf (-pi, pi].
    """

    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0


class LocalizationInterface(ABC):
    """Schnittstelle zur Roboterlokalisierung in der Zelle.

    Auf dem Zielsystem über LiDAR-Odometrie (``unilidar_sdk2`` +
    ``point_lio_unilidar``); hier Stub-Implementierung.
    """

    @abstractmethod
    def current_pose(self) -> Pose2D:
        """Liefert die aktuelle Roboterpose.

        Returns:
            Aktuelle ``Pose2D`` in Weltkoordinaten.
        """


class SimLocalization(LocalizationInterface):
    """Kinematischer Lokalisierungs-Stub für die Simulation.

    Integriert Geschwindigkeitsbefehle im Body-Frame und hält damit den
    internen Posezustand aktuell. Bietet perfekte Lokalisierung (kein Rauschen).

    Args:
        start: Startpose; bei None beginnt der Roboter in (0, 0, 0).
    """

    def __init__(self, start: Pose2D | None = None) -> None:
        self._p: Pose2D = Pose2D(
            x=start.x if start else 0.0,
            y=start.y if start else 0.0,
            theta=start.theta if start else 0.0,
        )

    def current_pose(self) -> Pose2D:
        """Liefert eine Kopie der aktuellen Pose.

        Returns:
            Kopie der internen ``Pose2D``.
        """
        return Pose2D(x=self._p.x, y=self._p.y, theta=self._p.theta)

    def integrate(self, vx: float, vy: float, omega: float, dt: float) -> None:
        """Aktualisiert die Pose anhand von Body-Frame-Geschwindigkeiten.

        Die Kinematik ist holonomisch (vollständiges omnidirektionales Modell):

            x' = x + (cos(theta)*vx - sin(theta)*vy) * dt
            y' = y + (sin(theta)*vx + cos(theta)*vy) * dt
            theta' = wrap_angle(theta + omega * dt)

        Args:
            vx:    Vorwärtsgeschwindigkeit im Body-Frame [m/s].
            vy:    Seitwärtsgeschwindigkeit im Body-Frame [m/s].
            omega: Winkelgeschwindigkeit [rad/s].
            dt:    Zeitschritt [s].
        """
        theta = self._p.theta
        self._p.x += (math.cos(theta) * vx - math.sin(theta) * vy) * dt
        self._p.y += (math.sin(theta) * vx + math.cos(theta) * vy) * dt
        self._p.theta = wrap_angle(theta + omega * dt)
