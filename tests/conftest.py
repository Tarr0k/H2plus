"""Gemeinsame Test-Fixtures: Mock-SPS und ein Sim-basierter Roboter."""

from __future__ import annotations

import pytest

from h2_loader.hal.arm import Arm
from h2_loader.hal.drivers.mujoco_sim_driver import MujocoSimDriver
from h2_loader.hal.end_effector.pneumatic_gripper import PneumaticGripper
from h2_loader.hal.end_effector.valve_actuator import H2IoValveActuator
from h2_loader.hal.robot import Robot
from h2_loader.plc.base import PlcInterface
from h2_loader.plc.signals import Signal


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
