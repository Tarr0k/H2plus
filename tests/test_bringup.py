"""Tests für den BringupSequencer — ausschließlich mit Mock-Komponenten.

Kein echter SDK-Import: alle Treiber/Sinks/Handshakes werden mit
``unittest.mock`` simuliert, damit diese Tests auf jeder Maschine ohne
``unitree_sdk2py`` laufen.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from h2_loader.bringup import BringupSequencer
from h2_loader.core.safety import SafetyGate
from h2_loader.hal.drivers.base import JointState


# ---------------------------------------------------------------------------
# Phase 0 — Netzwerk-Check (subprocess gemockt)
# ---------------------------------------------------------------------------

class TestPhase0Check:
    def test_ping_erfolgreich(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess, "run", MagicMock(return_value=MagicMock(returncode=0))
        )
        seq = BringupSequencer()
        assert seq.phase0_check("enp3s0", "192.168.123.161") is True

    def test_ping_fehlgeschlagen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            subprocess, "run", MagicMock(return_value=MagicMock(returncode=1))
        )
        seq = BringupSequencer()
        assert seq.phase0_check("enp3s0", "192.168.123.161") is False

    def test_ping_wirft_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=OSError("kein ping")))
        seq = BringupSequencer()
        assert seq.phase0_check("enp3s0") is False


# ---------------------------------------------------------------------------
# Phase 1 — DDS-Verbindung
# ---------------------------------------------------------------------------

class TestPhase1Dds:
    def test_erfolgreich_bei_7_plus_7_gelenken(self) -> None:
        driver = MagicMock()
        driver.read_state.return_value = JointState(positions={"left": [0.0] * 7, "right": [0.0] * 7})
        seq = BringupSequencer()
        assert seq.phase1_dds(driver) is True
        driver.connect.assert_called_once()

    def test_scheitert_bei_falscher_laenge(self) -> None:
        driver = MagicMock()
        driver.read_state.return_value = JointState(positions={"left": [0.0] * 3, "right": [0.0] * 7})
        seq = BringupSequencer()
        assert seq.phase1_dds(driver) is False

    def test_scheitert_bei_connect_exception(self) -> None:
        driver = MagicMock()
        driver.connect.side_effect = RuntimeError("keine Verbindung")
        seq = BringupSequencer()
        assert seq.phase1_dds(driver) is False


# ---------------------------------------------------------------------------
# Phase 2 — Locomotion-Bring-up
# ---------------------------------------------------------------------------

class TestPhase2Loco:
    def test_erfolgreich_mit_assume_yes(self) -> None:
        sink = MagicMock()
        seq = BringupSequencer()
        assert seq.phase2_loco(sink, assume_yes=True) is True
        sink.connect.assert_called_once()
        sink.bring_up.assert_called_once()

    def test_scheitert_bei_exception(self) -> None:
        sink = MagicMock()
        sink.bring_up.side_effect = RuntimeError("FSM-Fehler")
        seq = BringupSequencer()
        assert seq.phase2_loco(sink, assume_yes=True) is False


# ---------------------------------------------------------------------------
# Phase 3 — Arme in Home-Pose
# ---------------------------------------------------------------------------

class TestPhase3ArmHome:
    def test_erfolgreich_beide_arme(self) -> None:
        driver = MagicMock()
        safety = MagicMock()
        safety.is_clear.return_value = True
        home_pose = {"left": [0.0] * 7, "right": [0.0] * 7}
        seq = BringupSequencer()
        assert seq.phase3_arm_home(driver, home_pose, safety, assume_yes=True) is True
        assert driver.send_joints.call_count == 2

    def test_verweigert_ohne_sicherheitsfreigabe(self) -> None:
        driver = MagicMock()
        safety = MagicMock()
        safety.is_clear.return_value = False
        home_pose = {"left": [0.0] * 7, "right": [0.0] * 7}
        seq = BringupSequencer()
        assert seq.phase3_arm_home(driver, home_pose, safety, assume_yes=True) is False
        driver.send_joints.assert_not_called()

    def test_scheitert_bei_gesperrtem_send_joints(self) -> None:
        driver = MagicMock()
        driver.send_joints.side_effect = RuntimeError("enable_commanding=False")
        safety = SafetyGate()
        home_pose = {"left": [0.0] * 7, "right": [0.0] * 7}
        seq = BringupSequencer()
        assert seq.phase3_arm_home(driver, home_pose, safety, assume_yes=True) is False


# ---------------------------------------------------------------------------
# Phase 4 — SPS-Handshake
# ---------------------------------------------------------------------------

class TestPhase4Plc:
    def test_erfolgreich(self) -> None:
        handshake = MagicMock()
        handshake.read.return_value = 5
        seq = BringupSequencer()
        assert seq.phase4_plc(handshake) is True
        handshake.connect.assert_called_once()
        handshake.tick_heartbeat.assert_called_once()
        handshake.read.assert_called_once()

    def test_scheitert_bei_exception(self) -> None:
        handshake = MagicMock()
        handshake.connect.side_effect = RuntimeError("kein Endpunkt")
        seq = BringupSequencer()
        assert seq.phase4_plc(handshake) is False


# ---------------------------------------------------------------------------
# run() — Ablaufsteuerung
# ---------------------------------------------------------------------------

class TestRun:
    def test_bricht_bei_erster_fehlgeschlagener_phase_ab(self) -> None:
        seq = BringupSequencer()
        seq.phase1_dds = MagicMock(return_value=False)  # type: ignore[method-assign]
        seq.phase4_plc = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = seq.run([1, 4], assume_yes=True)

        assert result is False
        seq.phase1_dds.assert_called_once()
        seq.phase4_plc.assert_not_called()

    def test_fuehrt_alle_phasen_bei_erfolg_aus(self) -> None:
        seq = BringupSequencer()
        seq.phase1_dds = MagicMock(return_value=True)  # type: ignore[method-assign]
        seq.phase4_plc = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = seq.run([1, 4], assume_yes=True)

        assert result is True
        seq.phase1_dds.assert_called_once()
        seq.phase4_plc.assert_called_once()

    def test_unbekannte_phase_wirft_value_error(self) -> None:
        seq = BringupSequencer()
        with pytest.raises(ValueError):
            seq.run([99], assume_yes=True)
