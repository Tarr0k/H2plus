"""SPS-Simulator: spielt die Maschinen-/SPS-Seite des Handshake.

Ergänzt den ``H2HandshakeClient`` um die SPS-seitigen Aktionen:
  - Maschine als bereit melden (Betriebsmodus, Flags setzen).
  - SPS-Heartbeat ticken.
  - Auftrag senden (inkl. optionalem Signale-Seeding auf der Schritt-Ebene).
  - Done-Signal quittieren.
  - Vollständigen Zyklus in einem Aufruf: ``run_cycle``.

Nur für Simulation und Tests — kein Produktivcode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..util.logging import get_logger
from .base import PlcInterface
from .handshake import H2HandshakeClient
from .signals import Signal
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
        plc:       Optionaler Schritt-Ebene-Mock (MockPlc / OpcUaPlcClient)
                   für das Signal-Seeding der Skills.
    """

    def __init__(self, handshake: H2HandshakeClient, plc: PlcInterface | None = None) -> None:
        self._handshake = handshake
        self._plc = plc

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

        Verwendet ``sim_plc_send_job`` des Handshake-Clients und seedet
        anschließend die Schritt-Ebene-Signale für den jeweiligen Skill,
        sofern ein ``plc``-Objekt übergeben wurde.

        Args:
            req:       Auftragsart.
            job_id:    Eindeutige Job-ID.
            part_type: Bauteiltyp (Standard: 0).
        """
        self._handshake.sim_plc_send_job(req, job_id, part_type)
        _log.info("PlcSimulator: Auftrag gesendet — %s (jobId=%d, partType=%d)", req.name, job_id, part_type)

        if self._plc is None:
            return

        # Schritt-Ebene-Signale je Auftragsart vorbelegen
        if req == JobRequest.LOAD:
            self._plc.write_signal(Signal.DOOR_OPEN, True)
            self._plc.write_signal(Signal.FIXTURE_FREE, True)
            _log.debug("PlcSimulator: LOAD-Signale geseedet (DOOR_OPEN, FIXTURE_FREE)")
        elif req == JobRequest.UNLOAD:
            self._plc.write_signal(Signal.CYCLE_OK, True)
            self._plc.write_signal(Signal.DOOR_OPEN, True)
            _log.debug("PlcSimulator: UNLOAD-Signale geseedet (CYCLE_OK, DOOR_OPEN)")
        # Andere Auftragsarten: kein Seeding

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
