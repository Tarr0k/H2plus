"""Semantische Schritt-Ebene über die H2-UDT (MachineIo).

``MachineIo`` ist die Fassade, über die Skills die Maschine ansprechen.
Sie übersetzt lesbare Methoden (``door_open()``, ``request_close_clamp()``) auf
konkrete UDT-Member des ``H2HandshakeClient``.

Auf dem Zielsystem mappt jeder ``read``/``write``-Aufruf auf echte OPC-UA-Nodes
(Adressierung via ``udt.node_id``).  Im Stub/Test-Betrieb arbeitet der
``H2HandshakeClient`` im In-Memory-Modus.

Das flache ``Signal``/``PlcInterface``/``OpcUaPlcClient``-Ensemble ist LEGACY
und wird von den Skills nicht mehr genutzt (siehe ``signals.py``, ``base.py``,
``opcua_client.py``).
"""

from __future__ import annotations

from typing import Callable

from ..util.logging import get_logger
from .handshake import H2HandshakeClient

_log = get_logger(__name__)


class MachineIo:
    """Semantische Schritt-Ebene über den H2HandshakeClient.

    Kapselt alle maschinenrelevanten Lese-, Schreib- und Anforderungs-
    operationen, die ein Skill benötigt.  Statt roher UDT-Membernamen
    verwendet der Skill aussagekräftige Methoden wie ``door_open()`` oder
    ``request_close_clamp()``.

    Args:
        handshake:  Gemeinsam genutzter Handshake-Client.
        responder:  Optionaler Callback, der nach jeder Anforderung
                    aufgerufen wird.  Im Sim-Betrieb ist das
                    ``PlcSimulator.service_requests``; auf dem Zielsystem
                    entfällt der Callback (OPC-UA-Polling übernimmt das).
    """

    def __init__(
        self,
        handshake: H2HandshakeClient,
        responder: Callable[[], None] | None = None,
    ) -> None:
        self._hs = handshake
        self._responder = responder

    # ------------------------------------------------------------------
    # Lesen aus plcToRobot
    # ------------------------------------------------------------------

    def door_open(self) -> bool:
        """Tür ist geöffnet (plcToRobot.doorOpen)."""
        return bool(self._hs.read("plcToRobot", "doorOpen"))

    def door_closed(self) -> bool:
        """Tür ist geschlossen (plcToRobot.doorClosed)."""
        return bool(self._hs.read("plcToRobot", "doorClosed"))

    def clamp_open(self) -> bool:
        """Spannvorrichtung geöffnet (plcToRobot.clampOpen)."""
        return bool(self._hs.read("plcToRobot", "clampOpen"))

    def clamp_closed(self) -> bool:
        """Spannvorrichtung geschlossen (plcToRobot.clampClosed)."""
        return bool(self._hs.read("plcToRobot", "clampClosed"))

    def machine_ready(self) -> bool:
        """Maschine betriebsbereit (plcToRobot.machineReady)."""
        return bool(self._hs.read("plcToRobot", "machineReady"))

    def cycle_running(self) -> bool:
        """Bearbeitungszyklus läuft (plcToRobot.machineCycleRun)."""
        return bool(self._hs.read("plcToRobot", "machineCycleRun"))

    def cycle_done(self) -> bool:
        """Bearbeitungszyklus abgeschlossen (not plcToRobot.machineCycleRun)."""
        return not bool(self._hs.read("plcToRobot", "machineCycleRun"))

    def part_in_clamp(self) -> bool:
        """Werkstück ist gespannt (plcToRobot.partInClamp)."""
        return bool(self._hs.read("plcToRobot", "partInClamp"))

    def fixture_free(self) -> bool:
        """Spannvorrichtung frei — kein Werkstück (not plcToRobot.partInClamp)."""
        return not bool(self._hs.read("plcToRobot", "partInClamp"))

    def zone_free(self) -> bool:
        """Sicherheitszone für Roboter freigegeben (plcToRobot.zoneFreeForRobot)."""
        return bool(self._hs.read("plcToRobot", "zoneFreeForRobot"))

    def machine_fault(self) -> bool:
        """Maschinenalarm aktiv (plcToRobot.machineFault)."""
        return bool(self._hs.read("plcToRobot", "machineFault"))

    # ------------------------------------------------------------------
    # Roboter-Status schreiben (robotToPlc)
    # ------------------------------------------------------------------

    def set_current_step(self, step: int) -> None:
        """Schreibt den aktuellen Schrittzähler (robotToPlc.currentStep).

        Args:
            step: Aktueller Schrittzähler (0–32767).
        """
        self._hs.write("robotToPlc", "currentStep", step)
        _log.debug("MachineIo.set_current_step: %d", step)

    def set_gripper_holds(self, value: bool) -> None:
        """Setzt das Greifer-Hält-Werkstück-Flag (robotToPlc.gripperHoldsPart).

        Args:
            value: True, wenn der Greifer ein Werkstück hält.
        """
        self._hs.write("robotToPlc", "gripperHoldsPart", value)
        _log.debug("MachineIo.set_gripper_holds: %s", value)

    # ------------------------------------------------------------------
    # Anforderungen senden (robotToPlc + _service())
    # ------------------------------------------------------------------

    def request_open_door(self) -> None:
        """Fordert die SPS auf, die Tür zu öffnen (robotToPlc.reqOpenDoor)."""
        self._hs.write("robotToPlc", "reqOpenDoor", True)
        _log.info("MachineIo.request_open_door")
        self._service()

    def request_close_door(self) -> None:
        """Fordert die SPS auf, die Tür zu schließen (robotToPlc.reqCloseDoor)."""
        self._hs.write("robotToPlc", "reqCloseDoor", True)
        _log.info("MachineIo.request_close_door")
        self._service()

    def request_open_clamp(self) -> None:
        """Fordert die SPS auf, die Spannvorrichtung zu öffnen (robotToPlc.reqOpenClamp)."""
        self._hs.write("robotToPlc", "reqOpenClamp", True)
        _log.info("MachineIo.request_open_clamp")
        self._service()

    def request_close_clamp(self) -> None:
        """Fordert die SPS auf, die Spannvorrichtung zu schließen (robotToPlc.reqCloseClamp)."""
        self._hs.write("robotToPlc", "reqCloseClamp", True)
        _log.info("MachineIo.request_close_clamp")
        self._service()

    # ------------------------------------------------------------------
    # Warten (Stub: liest aktuellen Wert; Responder hat bereits reagiert)
    # ------------------------------------------------------------------

    def wait_door_open(self, timeout_s: float | None = None) -> bool:
        """Wartet, bis die Tür geöffnet ist.

        Im Stub-Betrieb liest der Responder bereits beim Anfordern den neuen
        Wert; daher genügt hier eine einfache Leseoperation.

        Args:
            timeout_s: Timeout in Sekunden (im Stub nicht ausgewertet).

        Returns:
            True, wenn die Tür geöffnet ist.
        """
        result = self.door_open()
        _log.debug("MachineIo.wait_door_open: %s", result)
        return result

    def wait_door_closed(self, timeout_s: float | None = None) -> bool:
        """Wartet, bis die Tür geschlossen ist.

        Args:
            timeout_s: Timeout in Sekunden (im Stub nicht ausgewertet).

        Returns:
            True, wenn die Tür geschlossen ist.
        """
        result = self.door_closed()
        _log.debug("MachineIo.wait_door_closed: %s", result)
        return result

    def wait_clamp_open(self, timeout_s: float | None = None) -> bool:
        """Wartet, bis die Spannvorrichtung geöffnet ist.

        Args:
            timeout_s: Timeout in Sekunden (im Stub nicht ausgewertet).

        Returns:
            True, wenn die Spannvorrichtung geöffnet ist.
        """
        result = self.clamp_open()
        _log.debug("MachineIo.wait_clamp_open: %s", result)
        return result

    def wait_clamp_closed(self, timeout_s: float | None = None) -> bool:
        """Wartet, bis die Spannvorrichtung geschlossen ist.

        Args:
            timeout_s: Timeout in Sekunden (im Stub nicht ausgewertet).

        Returns:
            True, wenn die Spannvorrichtung geschlossen ist.
        """
        result = self.clamp_closed()
        _log.debug("MachineIo.wait_clamp_closed: %s", result)
        return result

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    def _service(self) -> None:
        """Ruft den Responder auf, falls gesetzt.

        Auf dem Zielsystem würde hier OPC-UA gepollt bis die SPS reagiert.
        Im Sim/Test-Betrieb delegiert dies an ``PlcSimulator.service_requests``.
        """
        if self._responder is not None:
            self._responder()
