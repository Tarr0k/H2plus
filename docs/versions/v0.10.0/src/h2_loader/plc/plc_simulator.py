"""SPS-Simulator: spielt die Maschinen-/SPS-Seite des Handshake.

Ergänzt den ``H2HandshakeClient`` um die SPS-seitigen Aktionen:
  - Maschine als bereit melden (Betriebsmodus, Flags setzen).
  - SPS-Heartbeat ticken.
  - Auftrag senden (inkl. UDT-Maschinenzustand je Auftragsart).
  - Roboter-Anforderungen flankenartig konsumieren (``service_requests``).
  - Done-Signal quittieren.
  - Vollständigen Zyklus in einem Aufruf: ``run_cycle``.

Nur für Simulation und Tests — kein Produktivcode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..util.logging import get_logger
from .handshake import H2HandshakeClient
from .udt import JobRequest, OperatingMode

if TYPE_CHECKING:
    # Zirkelimport vermeiden: JobRunner nur für die Typ-Annotation
    from ..core.job_runner import JobRunner

_log = get_logger(__name__)


class PlcSimulator:
    """Simuliert die Maschinen-SPS über denselben ``H2HandshakeClient``.

    Spiegelbild zum ``JobRunner``: während der Runner die Roboter-Seite
    abbildet, bedient der Simulator die SPS-Seite — damit lässt sich ein
    vollständiger Zyklus ohne reale Hardware testen.

    Args:
        handshake: Gemeinsam genutzter Handshake-Client.
    """

    def __init__(self, handshake: H2HandshakeClient) -> None:
        self._handshake = handshake

    def set_machine_ready(self) -> None:
        """Meldet die Maschine als betriebsbereit.

        Setzt Betriebsmodus AUTO, ``robotConnected`` und ``machineReady``.
        Setzt zusätzlich die funktionalen Safety-Spiegel, damit der
        ``SafetySupervisor`` im Sim-Modus Freigabe erteilt.
        """
        self._handshake.write("control", "operatingMode", int(OperatingMode.AUTO))
        self._handshake.write("control", "robotConnected", True)
        self._handshake.write("plcToRobot", "machineReady", True)
        # Funktionale Safety-Spiegel für SafetySupervisor-Freigabe
        self._handshake.write("safety", "robotEnable",   True)
        self._handshake.write("safety", "safeZoneClear", True)
        self._handshake.write("safety", "watchdogFault", False)
        _log.debug(
            "PlcSimulator: Maschine bereit (AUTO, robotConnected, machineReady,"
            " robotEnable, safeZoneClear, watchdogFault=False)"
        )

    def tick_plc_heartbeat(self) -> None:
        """Erhöht ``plcHeartbeat`` um 1; Wrap-around bei 65535 → 0 (UInt)."""
        current = int(self._handshake.read("control", "plcHeartbeat"))
        self._handshake.write("control", "plcHeartbeat", (current + 1) % 65536)
        _log.debug("PlcSimulator: plcHeartbeat=%d", (current + 1) % 65536)

    def send_job(self, req: JobRequest, job_id: int, part_type: int = 0) -> None:
        """Sendet einen Auftrag an den Roboter.

        Verwendet ``sim_plc_send_job`` des Handshake-Clients und setzt
        anschließend den UDT-Maschinenzustand je Auftragsart in ``plcToRobot``.

        Args:
            req:       Auftragsart.
            job_id:    Eindeutige Job-ID.
            part_type: Bauteiltyp (Standard: 0).
        """
        self._handshake.sim_plc_send_job(req, job_id, part_type)
        _log.info("PlcSimulator: Auftrag gesendet — %s (jobId=%d, partType=%d)", req.name, job_id, part_type)

        if req == JobRequest.LOAD:
            self._handshake.write("plcToRobot", "doorOpen",       True)
            self._handshake.write("plcToRobot", "partInClamp",    False)
            self._handshake.write("plcToRobot", "machineCycleRun", False)
            self._handshake.write("plcToRobot", "clampOpen",      True)
            self._handshake.write("plcToRobot", "clampClosed",    False)
            _log.debug("PlcSimulator: LOAD-UDT-Zustand gesetzt (doorOpen, clampOpen, ~partInClamp)")
        elif req == JobRequest.UNLOAD:
            self._handshake.write("plcToRobot", "doorOpen",        True)
            self._handshake.write("plcToRobot", "machineCycleRun", False)
            self._handshake.write("plcToRobot", "partInClamp",     True)
            self._handshake.write("plcToRobot", "clampClosed",     True)
            self._handshake.write("plcToRobot", "clampOpen",       False)
            _log.debug("PlcSimulator: UNLOAD-UDT-Zustand gesetzt (doorOpen, clampClosed, partInClamp)")
        elif req == JobRequest.CHANGE_INDUCTOR:
            self._handshake.write("plcToRobot", "doorOpen",        True)
            self._handshake.write("plcToRobot", "machineReady",    True)
            self._handshake.write("plcToRobot", "machineCycleRun", False)
            _log.debug(
                "PlcSimulator: CHANGE_INDUCTOR-UDT-Zustand gesetzt "
                "(doorOpen, machineReady, ~machineCycleRun)"
            )

    def service_requests(self) -> None:
        """Konsumiert Roboter-Anforderungen flankenartig.

        Liest jedes req-Flag; ist es gesetzt, werden die entsprechenden
        Maschinenzustände in ``plcToRobot`` aktualisiert und das Flag
        anschließend auf False zurückgesetzt.
        """
        hs = self._handshake

        if bool(hs.read("robotToPlc", "reqOpenClamp")):
            hs.write("plcToRobot", "clampOpen",   True)
            hs.write("plcToRobot", "clampClosed", False)
            hs.write("plcToRobot", "partInClamp", False)
            hs.write("robotToPlc", "reqOpenClamp", False)
            _log.debug("PlcSimulator.service_requests: reqOpenClamp → clampOpen=True, partInClamp=False")

        if bool(hs.read("robotToPlc", "reqCloseClamp")):
            hs.write("plcToRobot", "clampClosed", True)
            hs.write("plcToRobot", "clampOpen",   False)
            hs.write("plcToRobot", "partInClamp", True)
            hs.write("robotToPlc", "reqCloseClamp", False)
            _log.debug("PlcSimulator.service_requests: reqCloseClamp → clampClosed=True, partInClamp=True")

        if bool(hs.read("robotToPlc", "reqOpenDoor")):
            hs.write("plcToRobot", "doorOpen",   True)
            hs.write("plcToRobot", "doorClosed", False)
            hs.write("robotToPlc", "reqOpenDoor", False)
            _log.debug("PlcSimulator.service_requests: reqOpenDoor → doorOpen=True")

        if bool(hs.read("robotToPlc", "reqCloseDoor")):
            hs.write("plcToRobot", "doorClosed", True)
            hs.write("plcToRobot", "doorOpen",   False)
            hs.write("robotToPlc", "reqCloseDoor", False)
            _log.debug("PlcSimulator.service_requests: reqCloseDoor → doorClosed=True")

    def acknowledge_done(self) -> None:
        """Quittiert das Done-Signal der SPS (robotState → IDLE)."""
        self._handshake.sim_plc_clear_done()
        _log.debug("PlcSimulator: Done quittiert")

    def run_cycle(
        self,
        runner: Any,  # JobRunner — via TYPE_CHECKING, kein harter Import
        req: JobRequest,
        job_id: int,
        part_type: int = 0,
    ) -> Any:  # JobOutcome | None
        """Führt einen vollständigen Zyklus durch.

        Ablauf:
            1. ``set_machine_ready()``
            2. ``tick_plc_heartbeat()``
            3. ``send_job(req, job_id, part_type)``
            4. ``runner.step()``
            5. ``acknowledge_done()``

        Args:
            runner:    JobRunner-Instanz, die den Roboter-Schritt ausführt.
            req:       Auftragsart.
            job_id:    Eindeutige Job-ID.
            part_type: Bauteiltyp (Standard: 0).

        Returns:
            Rückgabewert von ``runner.step()`` (``JobOutcome`` oder ``None``).
        """
        self.set_machine_ready()
        self.tick_plc_heartbeat()
        self.send_job(req, job_id, part_type)
        outcome = runner.step()
        self.acknowledge_done()
        return outcome
