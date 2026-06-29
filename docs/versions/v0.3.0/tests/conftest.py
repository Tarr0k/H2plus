"""Gemeinsame Test-Fixtures: Mock-SPS, Sim-Roboter und Sim-Locomotion."""

from __future__ import annotations

import pytest

from h2_loader.hal.arm import Arm
from h2_loader.hal.drivers.mujoco_sim_driver import MujocoSimDriver
from h2_loader.hal.end_effector.pneumatic_gripper import PneumaticGripper
from h2_loader.hal.end_effector.valve_actuator import H2IoValveActuator
from h2_loader.hal.locomotion.onboard_locomotion import OnboardLocomotion
from h2_loader.hal.robot import Robot
from h2_loader.plc.base import PlcInterface
from h2_loader.plc.signals import Signal
from h2_loader.util.config import Station


class MockPlc(PlcInterface):
    """In-Memory-SPS für Tests; Signale frei setzbar."""

    def __init__(self, initial: dict[Signal, bool] | None = None) -> None:
        self.state: dict[Signal, bool] = dict(initial or {})
        self.writes: list[tuple[Signal, bool]] = []

    def read_signal(self, signal: Signal) -> bool:
        return self.state.get(signal, False)

    def write_signal(self, signal: Signal, value: bool) -> None:
        self.state[signal] = value
        self.writes.append((signal, value))

    def wait_for(self, signal: Signal, value: bool = True, timeout_s: float | None = None) -> bool:
        return self.state.get(signal, False) == value


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


@pytest.fixture
def mock_plc() -> MockPlc:
    # Vorbedingungen für die Lade-Sequenz erfüllt.
    return MockPlc({Signal.DOOR_OPEN: True, Signal.FIXTURE_FREE: True})


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
