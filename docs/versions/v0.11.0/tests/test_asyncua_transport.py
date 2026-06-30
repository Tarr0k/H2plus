"""OPC-UA-Transport-Tests mit lokalem asyncua-Server (Loopback).

Alle Tests werden übersprungen (SKIPPED), wenn asyncua nicht installiert ist.
Damit bleibt die Default-Suite (157 Tests) ohne asyncua-Abhängigkeit grün.

Mit ``pip install "asyncua>=2.0"`` läuft ein echter OPC-UA-Server lokal
auf 127.0.0.1:48401 und belegt den vollständigen Roundtrip:
Transport → Server → Transport → H2HandshakeClient.
"""

from __future__ import annotations

import pytest

asyncua = pytest.importorskip("asyncua", exc_type=ImportError)

from asyncua import ua  # noqa: E402  # erst nach importorskip
from asyncua.sync import Client, Server  # noqa: E402

from h2_loader.plc.asyncua_transport import AsyncuaTransport  # noqa: E402
from h2_loader.plc.handshake import H2HandshakeClient  # noqa: E402
from h2_loader.plc.udt import FIELDS, JobRequest, JobResult, RobotState, node_id  # noqa: E402

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

_ENDPOINT = "opc.tcp://127.0.0.1:48401/h2test"
_DB_NAME = "H2_Interface_DB"
_NS = 3  # Namespace-Index, den der Server liefert (nach 2× register_namespace)

# Mapping TIA-Datentyp → ua.VariantType (spiegelt asyncua_transport.py)
_DTYPE_TO_VTYPE: dict[str, ua.VariantType] = {
    "Bool": ua.VariantType.Boolean,
    "Int":  ua.VariantType.Int16,
    "UInt": ua.VariantType.UInt16,
    "DInt": ua.VariantType.Int32,
}

# Standardwerte je Datentyp
_DTYPE_DEFAULTS: dict[str, int | bool] = {
    "Bool": False,
    "Int":  0,
    "UInt": 0,
    "DInt": 0,
}


# ---------------------------------------------------------------------------
# Server-Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def opc_server():
    """Startet einen lokalen asyncua-Server für alle Tests dieses Moduls.

    Namespace-Registrierung: asyncua-Server beginnt mit 2 Namespaces
    (Index 0 = OPC-Foundation, Index 1 = freeopcua-Default). Wir registrieren
    zwei weitere, sodass Index 3 existiert und mit _NS=3 konsistent ist.

    Für jeden FIELDS-Eintrag wird eine beschreibbare Variable-Node mit der
    exakten String-NodeId ``node_id(_DB_NAME, section, member, _NS)`` angelegt.
    """
    server = Server()
    server.set_endpoint(_ENDPOINT)
    server.start()

    # Sicherstellen, dass Namespace-Index _NS existiert
    ns_array = server.get_namespace_array()
    while len(ns_array) <= _NS:
        server.register_namespace("urn:ema:h2test:ns" + str(len(ns_array)))
        ns_array = server.get_namespace_array()

    objects = server.get_node(ua.ObjectIds.ObjectsFolder)

    # Alle UDT-Member als beschreibbare Nodes anlegen
    for field in FIELDS:
        nid_str = (
            f'"{_DB_NAME}"."iface"."{field.section}"."{field.name}"'
        )
        nid_obj = ua.NodeId(nid_str, _NS)
        vtype = _DTYPE_TO_VTYPE[field.dtype]
        default = _DTYPE_DEFAULTS[field.dtype]
        var = objects.add_variable(nid_obj, field.name, default, vtype)
        var.set_writable()

    yield server

    try:
        server.stop()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture()
def transport(opc_server: Server) -> AsyncuaTransport:  # noqa: ARG001
    """Liefert einen verbundenen AsyncuaTransport; trennt nach dem Test."""
    t = AsyncuaTransport(_ENDPOINT, db_name=_DB_NAME, ns=_NS)
    t.connect()
    yield t
    t.disconnect()


# ---------------------------------------------------------------------------
# Test 1: Primitiver read/write-Roundtrip via Transport
# ---------------------------------------------------------------------------

class TestAsyncuaTransportRoundtrip:
    """Direkte Lese-/Schreibzugriffe über AsyncuaTransport."""

    def test_write_read_uint(self, transport: AsyncuaTransport) -> None:
        """write + read für einen UInt-Member (plcHeartbeat) liefert den erwarteten Wert."""
        transport.write("control", "plcHeartbeat", 5)
        assert transport.read("control", "plcHeartbeat") == 5

    def test_write_read_bool(self, transport: AsyncuaTransport) -> None:
        """write + read für einen Bool-Member (safety.robotEnable) liefert True."""
        transport.write("safety", "robotEnable", True)
        assert transport.read("safety", "robotEnable") is True

    def test_write_read_dint(self, transport: AsyncuaTransport) -> None:
        """write + read für einen DInt-Member (robotToPlc.jobIdEcho) liefert den Wert."""
        transport.write("robotToPlc", "jobIdEcho", 999)
        assert transport.read("robotToPlc", "jobIdEcho") == 999

    def test_write_read_int(self, transport: AsyncuaTransport) -> None:
        """write + read für einen Int-Member (robotToPlc.robotState) liefert den Wert."""
        transport.write("robotToPlc", "robotState", int(RobotState.BUSY))
        assert transport.read("robotToPlc", "robotState") == int(RobotState.BUSY)


# ---------------------------------------------------------------------------
# Test 2: End-to-End-Handshake über OPC-UA
# ---------------------------------------------------------------------------

class TestHandshakeOverOpcUa:
    """Vollständiger Handshake-Zyklus via AsyncuaTransport + H2HandshakeClient."""

    def test_full_handshake_cycle(self, transport: AsyncuaTransport) -> None:
        """End-to-End: sim_plc_send_job → poll_job → accept_job → finish_job.

        Alle Werte werden physisch über den lokalen OPC-UA-Server gelesen
        und geschrieben. Damit ist der reale Transport-Roundtrip belegt.
        """
        hs = H2HandshakeClient(db_name=_DB_NAME, ns=_NS, transport=transport)

        # Sauberer Anfangszustand: alle relevanten Member zurücksetzen
        transport.write("plcToRobot", "jobReqToggle", False)
        transport.write("robotToPlc", "jobAckToggle", False)
        transport.write("robotToPlc", "jobDoneToggle", False)
        transport.write("robotToPlc", "robotState", int(RobotState.IDLE))
        transport.write("robotToPlc", "jobResult", int(JobResult.OPEN))

        # SPS sendet Auftrag (sim auf Roboter-Seite)
        hs.sim_plc_send_job(JobRequest.LOAD, 7, 0)

        # Roboter erkennt Auftrag
        job = hs.poll_job()
        assert job is not None, "poll_job sollte einen neuen Auftrag liefern"
        req, job_id, part_type = job
        assert req == JobRequest.LOAD
        assert job_id == 7
        assert part_type == 0

        # Roboter akzeptiert Auftrag
        hs.accept_job(7)

        # Zustand direkt vom OPC-UA-Server lesen (über Transport, nicht In-Memory)
        robot_state_raw = transport.read("robotToPlc", "robotState")
        assert robot_state_raw == int(RobotState.BUSY)

        req_toggle = transport.read("plcToRobot", "jobReqToggle")
        ack_toggle = transport.read("robotToPlc", "jobAckToggle")
        assert req_toggle == ack_toggle, "jobAckToggle muss nach accept_job dem jobReqToggle entsprechen"

        # Roboter meldet Auftrag als erledigt
        done_toggle_before = bool(transport.read("robotToPlc", "jobDoneToggle"))
        hs.finish_job(JobResult.OK)

        assert transport.read("robotToPlc", "jobResult") == int(JobResult.OK)
        assert transport.read("robotToPlc", "robotState") == int(RobotState.DONE)
        done_toggle_after = bool(transport.read("robotToPlc", "jobDoneToggle"))
        assert done_toggle_after != done_toggle_before, "jobDoneToggle muss invertiert werden"

        # kein weiterer Auftrag
        assert hs.poll_job() is None
