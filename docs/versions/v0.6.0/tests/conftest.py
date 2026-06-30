"""Gemeinsame Test-Fixtures: Sim-Umgebung, Sim-Roboter und Sim-Locomotion."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from h2_loader.hal.arm import Arm
from h2_loader.hal.drivers.mujoco_sim_driver import MujocoSimDriver
from h2_loader.hal.end_effector.pneumatic_gripper import PneumaticGripper
from h2_loader.hal.end_effector.valve_actuator import H2IoValveActuator
from h2_loader.hal.locomotion.onboard_locomotion import OnboardLocomotion
from h2_loader.hal.robot import Robot
from h2_loader.plc.handshake import H2HandshakeClient
from h2_loader.plc.machine_io import MachineIo
from h2_loader.plc.plc_simulator import PlcSimulator
from h2_loader.util.config import Station


@dataclass
class PlcEnv:
    """Gebündelte SPS-Testumgebung aus Handshake + Simulator + MachineIo."""

    handshake: H2HandshakeClient
    simulator: PlcSimulator
    machine: MachineIo


@pytest.fixture
def plc_env() -> PlcEnv:
    """Liefert eine frische SPS-Testumgebung (In-Memory-Handshake).

    Der Simulator ist als Responder in MachineIo eingehängt, sodass
    Anforderungen (request_close_clamp usw.) sofort den UDT-Zustand
    aktualisieren.
    """
    handshake = H2HandshakeClient()
    simulator = PlcSimulator(handshake)
    machine = MachineIo(handshake, responder=simulator.service_requests)
    return PlcEnv(handshake=handshake, simulator=simulator, machine=machine)


@pytest.fixture
def sim_robot() -> Robot:
    driver = MujocoSimDriver()
    arms = {
        side: Arm(side, driver, PneumaticGripper(H2IoValveActuator(channel=ch)))
        for side, ch in (("left", 0), ("right", 1))
    }
    robot = Robot(driver, arms)
    robot.connect()
    return robot


# Kleine Inline-Stationskarte für Tests (alle Stationen, die Skills benötigen).
_TEST_STATIONS: dict[str, Station] = {
    "home":           Station("home",           [0.0, 0.0, 0.0],    "Parkposition"),
    "part_storage":   Station("part_storage",   [2.0, 1.0, 1.57],   "Teilelager"),
    "machine":        Station("machine",        [0.0, 2.0, 0.0],    "Induktionshaertemaschine"),
    "dropoff_box":    Station("dropoff_box",    [-1.5, 1.0, -1.57], "Kiste fuer Fertigteile"),
    "inductor_shelf": Station("inductor_shelf", [1.5, -1.5, 0.78],  "Regal mit Induktoren"),
}


@pytest.fixture
def sim_locomotion() -> OnboardLocomotion:
    """OnboardLocomotion mit In-Memory-Stationskarte für Tests."""
    return OnboardLocomotion(_TEST_STATIONS)
