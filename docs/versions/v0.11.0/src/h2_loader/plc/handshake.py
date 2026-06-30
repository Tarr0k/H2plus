"""High-Level-Schnittstelle für den H2-Roboter-Handshake.

Der H2-Roboter ist OPC-UA-Client und liest/schreibt die TIA-UDT-Struktur
``H2Interface_UDT`` im Datenbaustein ``H2_Interface_DB``.

Transport-Strategie:
- Kein Transport (Standard): In-Memory-Zustandsspeicher — Handshake-Logik
  ohne reale SPS testbar (Sim/Test-Default).
- Transport gesetzt: ``read``/``write`` werden an den Transport delegiert
  (z. B. ``AsyncuaTransport`` für echten OPC-UA-Zugriff auf S7-1500).

Die High-Level-Methoden (``poll_job``, ``accept_job`` usw.) laufen transparent
über den jeweiligen Transport, ohne selbst geändert werden zu müssen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..util.logging import get_logger
from .udt import (
    FIELDS,
    JobRequest,
    JobResult,
    RobotState,
    node_id,
)

if TYPE_CHECKING:
    from .transport import HandshakeTransport

_log = get_logger(__name__)

# Standardwerte je Datentyp (passend zum Siemens-Verhalten nach Kaltstart)
_DTYPE_DEFAULTS: dict[str, int | bool] = {
    "Bool": False,
    "Int":  0,
    "UInt": 0,
    "DInt": 0,
}


def _default_state() -> dict[str, int | bool]:
    """Legt den Anfangs-Zustand aller UDT-Member an (alle 0/False)."""
    return {f"{f.section}.{f.name}": _DTYPE_DEFAULTS[f.dtype] for f in FIELDS}


class H2HandshakeClient:
    """Roboter-seitiger Handshake-Client.

    Kapselt die gesamte Toggle-/Heartbeat-Logik des H2-Roboter-Handshakes.

    Ohne ``transport``: In-Memory-Modus (Sim/Test) — alle Werte werden in
    einem internen Dict gehalten, keine externe Abhängigkeit nötig.

    Mit ``transport``: Alle ``read``/``write``-Aufrufe werden transparent an
    den Transport delegiert (z. B. ``AsyncuaTransport`` für S7-1500 via OPC-UA).
    ``connect()``/``disconnect()`` steuern in diesem Fall die Verbindung.

    Args:
        db_name:   Name des TIA-Interface-DBs.
        ns:        OPC-UA-Namespace-Index (Standard: 3).
        transport: Optionaler Transport (``HandshakeTransport``-Instanz).
                   ``None`` aktiviert den In-Memory-Modus.
    """

    def __init__(
        self,
        db_name: str = "H2_Interface_DB",
        ns: int = 3,
        transport: HandshakeTransport | None = None,
    ) -> None:
        self._db_name = db_name
        self._ns = ns
        self._transport = transport
        # Interner Zustand (nur im In-Memory-Modus genutzt)
        self._state: dict[str, int | bool] = _default_state()

    # ------------------------------------------------------------------
    # Verbindungsmanagement (delegiert an Transport, falls gesetzt)
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Öffnet die Verbindung zum Backend (nur relevant wenn Transport gesetzt)."""
        if self._transport is not None:
            self._transport.connect()
        else:
            _log.debug("H2HandshakeClient.connect: In-Memory-Modus, kein Transport")

    def disconnect(self) -> None:
        """Schließt die Verbindung zum Backend (nur relevant wenn Transport gesetzt)."""
        if self._transport is not None:
            self._transport.disconnect()
        else:
            _log.debug("H2HandshakeClient.disconnect: In-Memory-Modus, kein Transport")

    # ------------------------------------------------------------------
    # Generische Lese-/Schreibzugriffe
    # ------------------------------------------------------------------

    def read(self, section: str, member: str) -> int | bool:
        """Liest einen UDT-Member.

        Ist ein Transport gesetzt, wird der Wert vom Backend gelesen;
        sonst aus dem internen In-Memory-Zustand.

        Args:
            section: Sektion (z. B. ``"control"``).
            member:  Membername (z. B. ``"plcHeartbeat"``).

        Returns:
            Aktueller Wert (int oder bool).
        """
        if self._transport is not None:
            return self._transport.read(section, member)
        nid = node_id(self._db_name, section, member, self._ns)
        value = self._state[f"{section}.{member}"]
        _log.debug("read  %s = %r", nid, value)
        return value

    def write(self, section: str, member: str, value: int | bool) -> None:
        """Schreibt einen UDT-Member.

        Ist ein Transport gesetzt, wird der Wert ans Backend geschrieben;
        sonst in den internen In-Memory-Zustand.

        Args:
            section: Sektion.
            member:  Membername.
            value:   Neuer Wert.
        """
        if self._transport is not None:
            self._transport.write(section, member, value)
            return
        nid = node_id(self._db_name, section, member, self._ns)
        _log.debug("write %s = %r", nid, value)
        self._state[f"{section}.{member}"] = value

    # ------------------------------------------------------------------
    # Roboter-seitige High-Level-Methoden
    # ------------------------------------------------------------------

    def tick_heartbeat(self) -> None:
        """Erhöht ``robotHeartbeat`` um 1; Wrap-around bei 65535 → 0 (UInt)."""
        current = int(self.read("control", "robotHeartbeat"))
        self.write("control", "robotHeartbeat", (current + 1) % 65536)

    def poll_job(self) -> tuple[JobRequest, int, int] | None:
        """Prüft, ob ein neuer Auftrag vorliegt (Toggle-Mechanismus).

        Ein Auftrag ist neu, wenn ``jobReqToggle != jobAckToggle``.

        Returns:
            ``(JobRequest, job_id, part_type)`` oder ``None``, wenn kein
            neuer Auftrag wartet.
        """
        req_toggle = self.read("plcToRobot", "jobReqToggle")
        ack_toggle = self.read("robotToPlc", "jobAckToggle")
        if req_toggle == ack_toggle:
            return None
        job_req  = JobRequest(int(self.read("plcToRobot", "jobRequest")))
        job_id   = int(self.read("plcToRobot", "jobId"))
        part_type = int(self.read("plcToRobot", "partType"))
        _log.info("poll_job: neuer Auftrag %s (jobId=%d, partType=%d)", job_req.name, job_id, part_type)
        return job_req, job_id, part_type

    def accept_job(self, job_id: int) -> None:
        """Bestätigt einen Auftrag: Roboter wechselt in BUSY, quittiert Toggle.

        Args:
            job_id: Job-ID aus ``poll_job`` (wird als Echo zurückgeschrieben).
        """
        req_toggle = self.read("plcToRobot", "jobReqToggle")
        self.write("robotToPlc", "jobIdEcho",    job_id)
        self.write("robotToPlc", "robotState",   int(RobotState.BUSY))
        self.write("robotToPlc", "jobAckToggle", req_toggle)
        _log.info("accept_job: jobId=%d, robotState=BUSY", job_id)

    def finish_job(self, result: JobResult) -> None:
        """Meldet den Auftrag als abgeschlossen; invertiert ``jobDoneToggle``.

        Args:
            result: Ergebnis des Auftrags (OK / NOK / OPEN).
        """
        current_toggle = bool(self.read("robotToPlc", "jobDoneToggle"))
        self.write("robotToPlc", "jobResult",     int(result))
        self.write("robotToPlc", "robotState",    int(RobotState.DONE))
        self.write("robotToPlc", "jobDoneToggle", not current_toggle)
        _log.info("finish_job: result=%s, jobDoneToggle=%s", result.name, not current_toggle)

    def set_request(self, name: str, value: bool) -> None:
        """Setzt ein Anforderungs-Signal im ``robotToPlc``-Bereich.

        Typische Namen: ``reqOpenDoor``, ``reqCloseDoor``,
        ``reqOpenClamp``, ``reqCloseClamp``.

        Args:
            name:  Membername.
            value: Gewünschter Wert.
        """
        self.write("robotToPlc", name, value)

    def set_robot_in_machine(self, value: bool) -> None:
        """Setzt ``robotInMachine`` im ``robotToPlc``-Bereich.

        Args:
            value: True, wenn der Roboter sich im Maschinenbereich befindet.
        """
        self.write("robotToPlc", "robotInMachine", value)

    # ------------------------------------------------------------------
    # SPS-seitige Helfer (nur für Tests / Simulation)
    # ------------------------------------------------------------------

    def sim_plc_send_job(
        self,
        req: JobRequest,
        job_id: int,
        part_type: int,
    ) -> None:
        """Simuliert einen neuen Auftrag von der SPS.

        Setzt ``jobRequest``, ``jobId``, ``partType`` und invertiert
        ``jobReqToggle``, damit ``poll_job()`` einen neuen Auftrag erkennt.

        Args:
            req:       Auftragsart.
            job_id:    Eindeutige Job-ID.
            part_type: Bauteiltyp.
        """
        self.write("plcToRobot", "jobRequest",   int(req))
        self.write("plcToRobot", "jobId",        job_id)
        self.write("plcToRobot", "partType",     part_type)
        current_toggle = bool(self.read("plcToRobot", "jobReqToggle"))
        self.write("plcToRobot", "jobReqToggle", not current_toggle)
        _log.debug("sim_plc_send_job: %s jobId=%d partType=%d", req.name, job_id, part_type)

    def sim_plc_clear_done(self) -> None:
        """Simuliert das Quittieren des Done-Signals durch die SPS.

        Gleicht ``jobDoneToggle`` an (SPS hat das Ende gesehen) und
        setzt ``robotState`` auf IDLE.
        """
        done_toggle = self.read("robotToPlc", "jobDoneToggle")
        # In einer echten Implementierung würde die SPS intern quittieren;
        # hier setzen wir robotState zurück als sichtbares Zeichen.
        self.write("robotToPlc", "robotState", int(RobotState.IDLE))
        _log.debug("sim_plc_clear_done: robotState=IDLE (jobDoneToggle=%r)", done_toggle)
