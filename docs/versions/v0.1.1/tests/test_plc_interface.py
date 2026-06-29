"""Tests für UDT-Feldkatalog, NodeId-Konstruktion und Handshake-Logik.

Alle Tests laufen ohne reale Hardware (In-Memory-Stub).
"""

from __future__ import annotations

import pytest

from h2_loader.plc.handshake import H2HandshakeClient
from h2_loader.plc.udt import (
    FIELDS,
    Field,
    JobRequest,
    JobResult,
    OperatingMode,
    RobotState,
    node_id,
)


# ---------------------------------------------------------------------------
# node_id()
# ---------------------------------------------------------------------------

class TestNodeId:
    """Prüft den NodeId-String-Builder."""

    def test_exact_format(self) -> None:
        """node_id() liefert den exakten OPC-UA-String."""
        result = node_id("H2_Interface_DB", "control", "plcHeartbeat")
        assert result == 'ns=3;s="H2_Interface_DB"."iface"."control"."plcHeartbeat"'

    def test_custom_namespace(self) -> None:
        """Abweichender Namespace-Index wird korrekt eingebettet."""
        result = node_id("MyDB", "safety", "robotEnable", ns=5)
        assert result.startswith("ns=5;")

    def test_format_contains_all_parts(self) -> None:
        """Der String enthält DB-Name, IFACE_ROOT, Sektion und Member."""
        result = node_id("H2_Interface_DB", "robotToPlc", "jobIdEcho")
        assert '"H2_Interface_DB"' in result
        assert '"iface"' in result
        assert '"robotToPlc"' in result
        assert '"jobIdEcho"' in result


# ---------------------------------------------------------------------------
# Feldkatalog-Vollständigkeit
# ---------------------------------------------------------------------------

class TestFieldCatalog:
    """Prüft Anzahl, Sektionsverteilung und Eindeutigkeit der FIELDS."""

    def test_total_field_count(self) -> None:
        """Genau 41 Felder (7 + 13 + 16 + 5)."""
        assert len(FIELDS) == 41

    def test_control_field_count(self) -> None:
        """Sektion 'control' hat exakt 7 Member."""
        assert sum(1 for f in FIELDS if f.section == "control") == 7

    def test_plc_to_robot_field_count(self) -> None:
        """Sektion 'plcToRobot' hat exakt 13 Member."""
        assert sum(1 for f in FIELDS if f.section == "plcToRobot") == 13

    def test_robot_to_plc_field_count(self) -> None:
        """Sektion 'robotToPlc' hat exakt 16 Member."""
        assert sum(1 for f in FIELDS if f.section == "robotToPlc") == 16

    def test_safety_field_count(self) -> None:
        """Sektion 'safety' hat exakt 5 Member."""
        assert sum(1 for f in FIELDS if f.section == "safety") == 5

    def test_no_duplicate_keys(self) -> None:
        """Keine zwei Felder mit identischem (section, name)-Paar."""
        keys = [(f.section, f.name) for f in FIELDS]
        assert len(keys) == len(set(keys))

    def test_field_is_frozen_dataclass(self) -> None:
        """Field-Instanzen sind unveränderlich (frozen=True)."""
        f = Field("control", "plcAlive", "Bool")
        with pytest.raises(Exception):
            f.name = "x"  # type: ignore[misc]

    def test_all_dtypes_valid(self) -> None:
        """Alle Datentypen sind bekannte Siemens-Typen."""
        allowed = {"Bool", "Int", "UInt", "DInt"}
        for f in FIELDS:
            assert f.dtype in allowed, f"Unbekannter Typ '{f.dtype}' bei {f}"

    def test_known_member_present(self) -> None:
        """Stichprobe: erwartete Member sind vorhanden."""
        names_by_section: dict[str, set[str]] = {}
        for f in FIELDS:
            names_by_section.setdefault(f.section, set()).add(f.name)

        assert "plcHeartbeat"    in names_by_section["control"]
        assert "robotHeartbeat"  in names_by_section["control"]
        assert "jobRequest"      in names_by_section["plcToRobot"]
        assert "jobReqToggle"    in names_by_section["plcToRobot"]
        assert "robotState"      in names_by_section["robotToPlc"]
        assert "jobDoneToggle"   in names_by_section["robotToPlc"]
        assert "watchdogFault"   in names_by_section["safety"]


# ---------------------------------------------------------------------------
# IntEnum-Werte
# ---------------------------------------------------------------------------

class TestIntEnums:
    """Prüft die kodierten Enum-Werte."""

    def test_job_request_values(self) -> None:
        assert JobRequest.NONE            == 0
        assert JobRequest.LOAD            == 1
        assert JobRequest.UNLOAD          == 2
        assert JobRequest.CHANGE_INDUCTOR == 3

    def test_robot_state_values(self) -> None:
        assert RobotState.INIT      == 0
        assert RobotState.IDLE      == 1
        assert RobotState.BUSY      == 2
        assert RobotState.DONE      == 3
        assert RobotState.ERROR     == 4
        assert RobotState.NOT_READY == 5

    def test_job_result_values(self) -> None:
        assert JobResult.OPEN == 0
        assert JobResult.OK   == 1
        assert JobResult.NOK  == 2

    def test_operating_mode_values(self) -> None:
        assert OperatingMode.OFF    == 0
        assert OperatingMode.MANUAL == 1
        assert OperatingMode.AUTO   == 2
        assert OperatingMode.SETUP  == 3


# ---------------------------------------------------------------------------
# H2HandshakeClient — Basis
# ---------------------------------------------------------------------------

class TestHandshakeClientBasics:
    """Prüft Initialisierung und generische read/write-Zugriffe."""

    def test_initial_state_all_zero(self) -> None:
        """Alle Member sind nach Initialisierung 0 oder False."""
        client = H2HandshakeClient()
        for f in FIELDS:
            value = client.read(f.section, f.name)
            assert value == 0 or value is False, (
                f"Unerwartet gesetzter Anfangswert bei {f.section}.{f.name}: {value!r}"
            )

    def test_write_read_roundtrip(self) -> None:
        """Geschriebener Wert ist anschließend lesbar."""
        client = H2HandshakeClient()
        client.write("control", "operatingMode", 2)
        assert client.read("control", "operatingMode") == 2

    def test_write_bool(self) -> None:
        """Bool-Felder nehmen True/False an."""
        client = H2HandshakeClient()
        client.write("safety", "robotEnable", True)
        assert client.read("safety", "robotEnable") is True


# ---------------------------------------------------------------------------
# tick_heartbeat
# ---------------------------------------------------------------------------

class TestTickHeartbeat:
    """Prüft Heartbeat-Erhöhung und UInt-Wrap."""

    def test_increments_by_one(self) -> None:
        """tick_heartbeat erhöht robotHeartbeat von 0 auf 1."""
        client = H2HandshakeClient()
        client.tick_heartbeat()
        assert client.read("control", "robotHeartbeat") == 1

    def test_multiple_ticks(self) -> None:
        """Mehrfaches Ticken addiert sich korrekt auf."""
        client = H2HandshakeClient()
        for _ in range(5):
            client.tick_heartbeat()
        assert client.read("control", "robotHeartbeat") == 5

    def test_wrap_at_65535(self) -> None:
        """UInt-Wrap: 65535 + 1 ergibt 0."""
        client = H2HandshakeClient()
        client.write("control", "robotHeartbeat", 65535)
        client.tick_heartbeat()
        assert client.read("control", "robotHeartbeat") == 0


# ---------------------------------------------------------------------------
# Vollständige Toggle-Handshake-Sequenz
# ---------------------------------------------------------------------------

class TestHandshakeSequence:
    """Prüft den kompletten Auftragszyklus über sim_plc_send_job → finish_job."""

    def test_no_job_initially(self) -> None:
        """poll_job liefert None, wenn kein Auftrag vorliegt."""
        client = H2HandshakeClient()
        assert client.poll_job() is None

    def test_poll_job_detects_new_job(self) -> None:
        """Nach sim_plc_send_job erkennt poll_job einen neuen Auftrag."""
        client = H2HandshakeClient()
        client.sim_plc_send_job(JobRequest.LOAD, job_id=42, part_type=1)
        result = client.poll_job()
        assert result is not None
        req, job_id, part_type = result
        assert req      == JobRequest.LOAD
        assert job_id   == 42
        assert part_type == 1

    def test_accept_job_sets_busy_and_ack(self) -> None:
        """accept_job setzt robotState=BUSY und gleicht jobAckToggle an."""
        client = H2HandshakeClient()
        client.sim_plc_send_job(JobRequest.LOAD, job_id=42, part_type=1)
        _, job_id, _ = client.poll_job()  # type: ignore[misc]

        client.accept_job(job_id)

        assert client.read("robotToPlc", "robotState")   == int(RobotState.BUSY)
        assert client.read("robotToPlc", "jobIdEcho")    == 42
        # Nach accept muss jobAckToggle == jobReqToggle sein
        req_toggle = client.read("plcToRobot", "jobReqToggle")
        ack_toggle = client.read("robotToPlc", "jobAckToggle")
        assert req_toggle == ack_toggle

    def test_no_new_job_after_accept(self) -> None:
        """poll_job liefert None, nachdem accept_job den Toggle angeglichen hat."""
        client = H2HandshakeClient()
        client.sim_plc_send_job(JobRequest.LOAD, job_id=1, part_type=0)
        _, job_id, _ = client.poll_job()  # type: ignore[misc]
        client.accept_job(job_id)
        assert client.poll_job() is None

    def test_finish_job_sets_done_and_toggles(self) -> None:
        """finish_job setzt jobResult=OK, robotState=DONE, invertiert jobDoneToggle."""
        client = H2HandshakeClient()
        client.sim_plc_send_job(JobRequest.LOAD, job_id=7, part_type=2)
        _, job_id, _ = client.poll_job()  # type: ignore[misc]
        client.accept_job(job_id)

        toggle_before = bool(client.read("robotToPlc", "jobDoneToggle"))
        client.finish_job(JobResult.OK)

        assert client.read("robotToPlc", "jobResult")    == int(JobResult.OK)
        assert client.read("robotToPlc", "robotState")   == int(RobotState.DONE)
        toggle_after = bool(client.read("robotToPlc", "jobDoneToggle"))
        assert toggle_after != toggle_before

    def test_full_cycle(self) -> None:
        """Vollständiger Zyklus: send→poll→accept→finish mit Zustandsüberprüfung."""
        client = H2HandshakeClient()

        # SPS sendet Auftrag
        client.sim_plc_send_job(JobRequest.UNLOAD, job_id=99, part_type=3)

        # Roboter erkennt Auftrag
        job = client.poll_job()
        assert job is not None
        req, job_id, part_type = job
        assert req == JobRequest.UNLOAD
        assert job_id == 99

        # Roboter nimmt Auftrag an
        client.accept_job(job_id)
        assert client.read("robotToPlc", "robotState") == int(RobotState.BUSY)

        # Toggle ist angeglichen → kein weiterer Auftrag sichtbar
        assert client.poll_job() is None

        # Roboter schließt Auftrag ab (NOK)
        client.finish_job(JobResult.NOK)
        assert client.read("robotToPlc", "jobResult")  == int(JobResult.NOK)
        assert client.read("robotToPlc", "robotState") == int(RobotState.DONE)

    def test_sim_plc_clear_done_resets_to_idle(self) -> None:
        """sim_plc_clear_done setzt robotState auf IDLE."""
        client = H2HandshakeClient()
        client.sim_plc_send_job(JobRequest.LOAD, job_id=1, part_type=0)
        _, job_id, _ = client.poll_job()  # type: ignore[misc]
        client.accept_job(job_id)
        client.finish_job(JobResult.OK)

        client.sim_plc_clear_done()
        assert client.read("robotToPlc", "robotState") == int(RobotState.IDLE)

    def test_toggle_persists_across_two_jobs(self) -> None:
        """Zwei aufeinanderfolgende Aufträge werden korrekt erkannt (Toggle-Persistenz)."""
        client = H2HandshakeClient()

        for i in range(1, 3):
            client.sim_plc_send_job(JobRequest.LOAD, job_id=i, part_type=0)
            job = client.poll_job()
            assert job is not None
            _, job_id, _ = job
            client.accept_job(job_id)
            client.finish_job(JobResult.OK)
            client.sim_plc_clear_done()


# ---------------------------------------------------------------------------
# set_request / set_robot_in_machine
# ---------------------------------------------------------------------------

class TestSetHelpers:
    """Prüft die Signal-Setter-Helfer."""

    def test_set_request_req_open_door(self) -> None:
        client = H2HandshakeClient()
        client.set_request("reqOpenDoor", True)
        assert client.read("robotToPlc", "reqOpenDoor") is True

    def test_set_request_req_close_clamp(self) -> None:
        client = H2HandshakeClient()
        client.set_request("reqCloseClamp", True)
        assert client.read("robotToPlc", "reqCloseClamp") is True

    def test_set_robot_in_machine(self) -> None:
        client = H2HandshakeClient()
        client.set_robot_in_machine(True)
        assert client.read("robotToPlc", "robotInMachine") is True

    def test_set_robot_in_machine_false(self) -> None:
        client = H2HandshakeClient()
        client.set_robot_in_machine(True)
        client.set_robot_in_machine(False)
        assert client.read("robotToPlc", "robotInMachine") is False
