"""Tests für OnboardLocomotion: Stationen anfahren, unbekannte Station, Sequenz."""

from __future__ import annotations

import pytest

from h2_loader.hal.locomotion.onboard_locomotion import OnboardLocomotion
from h2_loader.util.config import Station

# Kleine Stationskarte ausschließlich für dieses Testmodul.
_STATIONS: dict[str, Station] = {
    "home":         Station("home",         [0.0, 0.0, 0.0],   "Parkposition"),
    "part_storage": Station("part_storage", [2.0, 1.0, 1.57],  "Teilelager"),
    "machine":      Station("machine",      [0.0, 2.0, 0.0],   "Induktionshaertemaschine"),
    "dropoff_box":  Station("dropoff_box",  [-1.5, 1.0, -1.57], "Kiste fuer Fertigteile"),
}


@pytest.fixture
def loco() -> OnboardLocomotion:
    """OnboardLocomotion ohne Treiber (reiner Stub) für die Tests."""
    return OnboardLocomotion(_STATIONS)


def test_move_to_known_station_returns_true(loco: OnboardLocomotion) -> None:
    """move_to eine bekannte Station liefert True."""
    result = loco.move_to("part_storage")
    assert result is True


def test_move_to_updates_current_station(loco: OnboardLocomotion) -> None:
    """Nach move_to zeigt current_station() die angefahrene Station."""
    loco.move_to("part_storage")
    assert loco.current_station() == "part_storage"


def test_initial_current_station_is_none(loco: OnboardLocomotion) -> None:
    """Vor dem ersten move_to ist current_station() None."""
    assert loco.current_station() is None


def test_move_to_unknown_station_raises_key_error(loco: OnboardLocomotion) -> None:
    """move_to eine unbekannte Station wirft einen KeyError."""
    with pytest.raises(KeyError):
        loco.move_to("unbekannte_station")


def test_key_error_message_contains_station_name(loco: OnboardLocomotion) -> None:
    """Die KeyError-Meldung enthält den fehlerhaften Stationsnamen."""
    with pytest.raises(KeyError, match="unbekannte_station"):
        loco.move_to("unbekannte_station")


def test_multistep_current_station_follows_last(loco: OnboardLocomotion) -> None:
    """Nacheinander zwei Stationen anfahren; current_station folgt der letzten."""
    loco.move_to("part_storage")
    assert loco.current_station() == "part_storage"

    loco.move_to("machine")
    assert loco.current_station() == "machine"


def test_multistep_all_three_stations(loco: OnboardLocomotion) -> None:
    """Drei Stationen in Sequenz; jede Rückgabe ist True, zuletzt current_station korrekt."""
    for station in ("home", "dropoff_box", "machine"):
        result = loco.move_to(station)
        assert result is True
    assert loco.current_station() == "machine"


def test_stop_does_not_clear_current_station(loco: OnboardLocomotion) -> None:
    """stop() ändert current_station() nicht (Stub-Verhalten)."""
    loco.move_to("home")
    loco.stop()
    assert loco.current_station() == "home"
