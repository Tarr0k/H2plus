"""Velocity-Sink-Interface und Implementierungen für den H2-Navigationregler.

Ein ``VelocitySink`` empfängt Geschwindigkeitsbefehle vom Regler und leitet
sie ans jeweilige Backend weiter — in der Simulation an ``SimLocalization.integrate``,
auf der echten Hardware an ``LocoClient.Move`` (Stub).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...util.logging import get_logger
from .localization import SimLocalization

_log = get_logger(__name__)


class VelocitySink(ABC):
    """Schnittstelle zum Absenden von Geschwindigkeitsbefehlen.

    Der Navigationregler ruft ``send_velocity`` in jedem Regelzyklus auf und
    ``stop`` beim Beenden einer Fahrt (Ziel erreicht oder Abbruch).
    """

    @abstractmethod
    def send_velocity(self, vx: float, vy: float, omega: float) -> None:
        """Sendet einen Geschwindigkeitsbefehl.

        Args:
            vx:    Vorwärtsgeschwindigkeit im Body-Frame [m/s].
            vy:    Seitwärtsgeschwindigkeit im Body-Frame [m/s].
            omega: Winkelgeschwindigkeit [rad/s].
        """

    @abstractmethod
    def stop(self) -> None:
        """Stoppt die Bewegung (vx=vy=omega=0)."""


class SimVelocitySink(VelocitySink):
    """Velocity-Sink für die Simulation — delegiert an ``SimLocalization.integrate``.

    Args:
        localization: Die Simulationslokalisierung, deren Pose integriert wird.
        dt:           Zeitschritt für die kinematische Integration [s].
    """

    def __init__(self, localization: SimLocalization, dt: float) -> None:
        self._loc = localization
        self._dt = dt

    def send_velocity(self, vx: float, vy: float, omega: float) -> None:
        """Integriert den Befehl in die Simulationspose.

        Args:
            vx:    Vorwärtsgeschwindigkeit [m/s].
            vy:    Seitwärtsgeschwindigkeit [m/s].
            omega: Winkelgeschwindigkeit [rad/s].
        """
        self._loc.integrate(vx, vy, omega, self._dt)

    def stop(self) -> None:
        """Integriert einen Null-Geschwindigkeitsbefehl (Pose bleibt unverändert)."""
        self._loc.integrate(0.0, 0.0, 0.0, self._dt)


class LocoClientVelocitySink(VelocitySink):
    """Velocity-Sink für die echte Hardware — Stub für ``LocoClient.Move``.

    Auf dem Zielsystem würde diese Klasse ``unitree_sdk2py.h2.loco.h2_loco_client.LocoClient``
    importieren und ``LocoClient.Move(vx, vy, omega)`` bzw. ``LocoClient.StopMove``
    aufrufen. Im Stub-Stand wird nur geloggt.

    Args:
        loco_client: Platzhalter — im echten Betrieb die ``LocoClient``-Instanz.
    """

    def __init__(self, loco_client: object | None = None) -> None:
        self._client = loco_client

    def send_velocity(self, vx: float, vy: float, omega: float) -> None:
        """Würde ``LocoClient.Move(vx, vy, omega)`` aufrufen (Stub: Log).

        Args:
            vx:    Vorwärtsgeschwindigkeit [m/s].
            vy:    Seitwärtsgeschwindigkeit [m/s].
            omega: Winkelgeschwindigkeit [rad/s].
        """
        _log.debug("LocoClientVelocitySink.send_velocity: vx=%.3f vy=%.3f omega=%.3f (Stub)", vx, vy, omega)

    def stop(self) -> None:
        """Würde ``LocoClient.StopMove`` aufrufen (Stub: Log)."""
        _log.debug("LocoClientVelocitySink.stop — StopMove (Stub)")
