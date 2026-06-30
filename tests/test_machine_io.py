"""Tests für MachineIo: Lese-Mapping, Anforderungen und Responder-Integration."""

from __future__ import annotations

from h2_loader.plc.handshake import H2HandshakeClient
from h2_loader.plc.machine_io import MachineIo
from h2_loader.plc.plc_simulator import PlcSimulator


# ---------------------------------------------------------------------------
# Lese-Mapping (plcToRobot → MachineIo-Methoden)
# ---------------------------------------------------------------------------

def test_door_open_spiegelt_udt(plc_env) -> None:
    plc_env.handshake.write("plcToRobot", "doorOpen", True)
    assert plc_env.machine.door_open() is True
    plc_env.handshake.write("plcToRobot", "doorOpen", False)
    assert plc_env.machine.door_open() is False


def test_door_closed_spiegelt_udt(plc_env) -> None:
    plc_env.handshake.write("plcToRobot", "doorClosed", True)
    assert plc_env.machine.door_closed() is True


def test_fixture_free_ist_invers_zu_part_in_clamp(plc_env) -> None:
    plc_env.handshake.write("plcToRobot", "partInClamp", False)
    assert plc_env.machine.fixture_free() is True
    assert plc_env.machine.part_in_clamp() is False

    plc_env.handshake.write("plcToRobot", "partInClamp", True)
    assert plc_env.machine.fixture_free() is False
    assert plc_env.machine.part_in_clamp() is True


def test_cycle_done_ist_invers_zu_cycle_running(plc_env) -> None:
    plc_env.handshake.write("plcToRobot", "machineCycleRun", True)
    assert plc_env.machine.cycle_running() is True
    assert plc_env.machine.cycle_done() is False

    plc_env.handshake.write("plcToRobot", "machineCycleRun", False)
    assert plc_env.machine.cycle_running() is False
    assert plc_env.machine.cycle_done() is True


def test_zone_free_und_machine_fault(plc_env) -> None:
    plc_env.handshake.write("plcToRobot", "zoneFreeForRobot", True)
    assert plc_env.machine.zone_free() is True

    plc_env.handshake.write("plcToRobot", "machineFault", True)
    assert plc_env.machine.machine_fault() is True


# ---------------------------------------------------------------------------
# Schreib-Methoden (robotToPlc)
# ---------------------------------------------------------------------------

def test_set_current_step_schreibt_durch(plc_env) -> None:
    plc_env.machine.set_current_step(42)
    assert int(plc_env.handshake.read("robotToPlc", "currentStep")) == 42


def test_set_gripper_holds_schreibt_durch(plc_env) -> None:
    plc_env.machine.set_gripper_holds(True)
    assert bool(plc_env.handshake.read("robotToPlc", "gripperHoldsPart")) is True

    plc_env.machine.set_gripper_holds(False)
    assert bool(plc_env.handshake.read("robotToPlc", "gripperHoldsPart")) is False


# ---------------------------------------------------------------------------
# Anforderungen mit Responder (PlcSimulator.service_requests)
# ---------------------------------------------------------------------------

def test_request_close_clamp_via_responder(plc_env) -> None:
    """request_close_clamp + service_requests → clamp_closed=True, part_in_clamp=True."""
    plc_env.machine.request_close_clamp()
    assert plc_env.machine.clamp_closed() is True
    assert plc_env.machine.part_in_clamp() is True
    assert plc_env.machine.clamp_open() is False
    assert plc_env.machine.fixture_free() is False
    # req-Flag muss zurückgesetzt sein
    assert bool(plc_env.handshake.read("robotToPlc", "reqCloseClamp")) is False


def test_request_open_clamp_via_responder(plc_env) -> None:
    """request_open_clamp + service_requests → clamp_open=True, fixture_free=True."""
    # Zuerst schließen, dann wieder öffnen
    plc_env.machine.request_close_clamp()
    plc_env.machine.request_open_clamp()
    assert plc_env.machine.clamp_open() is True
    assert plc_env.machine.fixture_free() is True
    assert plc_env.machine.part_in_clamp() is False
    assert bool(plc_env.handshake.read("robotToPlc", "reqOpenClamp")) is False


def test_request_open_door_via_responder(plc_env) -> None:
    """request_open_door + service_requests → door_open=True."""
    plc_env.machine.request_open_door()
    assert plc_env.machine.door_open() is True
    assert plc_env.machine.door_closed() is False
    assert bool(plc_env.handshake.read("robotToPlc", "reqOpenDoor")) is False


def test_request_close_door_via_responder(plc_env) -> None:
    """request_close_door + service_requests → door_closed=True."""
    plc_env.machine.request_close_door()
    assert plc_env.machine.door_closed() is True
    assert plc_env.machine.door_open() is False
    assert bool(plc_env.handshake.read("robotToPlc", "reqCloseDoor")) is False


# ---------------------------------------------------------------------------
# MachineIo ohne Responder: req-Flag bleibt gesetzt
# ---------------------------------------------------------------------------

def test_kein_responder_req_flag_bleibt(plc_env) -> None:
    """Ohne Responder bleibt das req-Flag gesetzt (kein Auto-Service)."""
    handshake = H2HandshakeClient()
    machine_no_resp = MachineIo(handshake)
    machine_no_resp.request_close_clamp()
    # Flag gesetzt, aber Zustand nicht verändert (kein Responder)
    assert bool(handshake.read("robotToPlc", "reqCloseClamp")) is True
    assert bool(handshake.read("plcToRobot", "clampClosed")) is False


# ---------------------------------------------------------------------------
# Wait-Methoden (Stub: liest aktuellen Wert nach service)
# ---------------------------------------------------------------------------

def test_wait_clamp_closed_nach_request(plc_env) -> None:
    plc_env.machine.request_close_clamp()
    assert plc_env.machine.wait_clamp_closed() is True


def test_wait_clamp_open_nach_request(plc_env) -> None:
    # Erst schließen, dann öffnen
    plc_env.machine.request_close_clamp()
    plc_env.machine.request_open_clamp()
    assert plc_env.machine.wait_clamp_open() is True


def test_wait_door_open_nach_request(plc_env) -> None:
    plc_env.machine.request_open_door()
    assert plc_env.machine.wait_door_open() is True


def test_wait_door_closed_nach_request(plc_env) -> None:
    plc_env.machine.request_close_door()
    assert plc_env.machine.wait_door_closed() is True
