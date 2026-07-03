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
    """Velocity-Sink für die echte Hardware — bindet ``LocoClient.Move`` an.

    ⚠️ HARDWARE-UNTESTED — entspricht den ``unitree_sdk2py``-h2-Beispielen
    (siehe docs/sdk_reference.md), aber noch nie gegen echte Hardware
    verifiziert. Vor dem ersten Reallauf jede Zeile gegenprüfen.

    NUR mit aktivem **Debug-Modus** an der Fernbedienung betreiben
    (L2+R2 aktivieren, L2+A bestätigen, L2+B Notfall-Damping) — ohne
    Debug-Modus kollidiert der Befehl mit dem automatisch laufenden
    Motion-Control-Programm (Zittern).

    Der SDK-Import erfolgt lazy in ``connect()``, damit dieses Modul auch
    ohne installiertes ``unitree_sdk2py`` importierbar bleibt.

    Args:
        network_interface: Ethernet-Interface für die DDS-Kommunikation
            (z. B. ``"enp3s0"``); ``None`` lässt ``ChannelFactoryInitialize``
            das Standard-Interface wählen.
        domain_id: DDS-Domain-ID (0 = real, 1 = Sim/Loopback laut SDK-Konvention).
    """

    def __init__(self, network_interface: str | None = None, domain_id: int = 0) -> None:
        self._iface = network_interface
        self._domain_id = domain_id
        self._client: object | None = None

    def connect(self) -> None:
        """Initialisiert den DDS-Kanal und den ``LocoClient`` (lazy SDK-Import).

        Raises:
            ImportError: wenn ``unitree_sdk2py`` auf diesem Rechner nicht installiert ist.
        """
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize  # noqa: PLC0415  # Lazy-Import bewusst
        from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient  # noqa: PLC0415

        _log.warning(
            "LocoClientVelocitySink.connect: Hardware-untested — NUR im aktiven Debug-Modus "
            "betreiben (L2+R2 aktivieren, L2+A bestaetigen, L2+B Not-Damping)."
        )

        if self._iface:
            ChannelFactoryInitialize(self._domain_id, self._iface)
        else:
            ChannelFactoryInitialize(self._domain_id)

        client = LocoClient()
        client.SetTimeout(10.0)
        client.Init()
        self._client = client
        _log.info("LocoClientVelocitySink: verbunden (domain_id=%d, iface=%s)", self._domain_id, self._iface)

    def bring_up(self) -> None:
        """Fährt die FSM-Hochfahrsequenz Damp → Start → StandUp.

        ⚠️ SICHERHEIT: Der Roboter bewegt sich (steht auf) — NUR im Debug-Modus
        und mit freiem Umfeld aufrufen. ``Damp`` zuerst, um aus einem
        undefinierten Zustand sicher zu starten.

        Raises:
            RuntimeError: wenn ``connect()`` noch nicht aufgerufen wurde.
        """
        if self._client is None:
            raise RuntimeError("LocoClientVelocitySink.bring_up: connect() fehlt")
        _log.warning("LocoClientVelocitySink.bring_up: Damp -> Start -> StandUp — Roboter bewegt sich!")
        self._client.Damp()  # type: ignore[attr-defined]
        self._client.Start()  # type: ignore[attr-defined]
        self._client.StandUp()  # type: ignore[attr-defined]
        _log.info("LocoClientVelocitySink.bring_up: FSM hochgefahren (Damp/Start/StandUp)")

    def send_velocity(self, vx: float, vy: float, omega: float) -> None:
        """Sendet einen Geschwindigkeitsbefehl über ``LocoClient.Move``.

        Args:
            vx:    Vorwärtsgeschwindigkeit im Body-Frame [m/s].
            vy:    Seitwärtsgeschwindigkeit im Body-Frame [m/s].
            omega: Winkelgeschwindigkeit [rad/s].

        Raises:
            RuntimeError: wenn ``connect()`` noch nicht aufgerufen wurde.
        """
        if self._client is None:
            raise RuntimeError("LocoClientVelocitySink.send_velocity: connect() fehlt")
        self._client.Move(vx, vy, omega)  # type: ignore[attr-defined]

    def stop(self) -> None:
        """Sendet ``LocoClient.StopMove``.

        Raises:
            RuntimeError: wenn ``connect()`` noch nicht aufgerufen wurde.
        """
        if self._client is None:
            raise RuntimeError("LocoClientVelocitySink.stop: connect() fehlt")
        self._client.StopMove()  # type: ignore[attr-defined]
