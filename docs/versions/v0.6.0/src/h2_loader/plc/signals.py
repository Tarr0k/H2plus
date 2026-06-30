"""Symbolische SPS-Signale für den Maschinen-Handshake.

.. note::
    LEGACY — durch die UDT-Schritt-Ebene ``plc.machine_io.MachineIo`` ersetzt;
    bleibt aus Kompatibilität erhalten, wird von den Skills nicht mehr genutzt.

Die konkreten Adressen/NodeIds liegen in ``config/plc.yaml`` (Mapping
Signal-Name -> Adresse). Im Code wird nur über diese Enum referenziert, damit
der Handshake lesbar bleibt: "warte bis DOOR_OPEN" statt roher Adressen.
"""

from __future__ import annotations

from enum import Enum


class Signal(str, Enum):
    """Bekannte SPS-Signale der Induktionshärtemaschine."""

    DOOR_OPEN = "door_open"               # Maschinentür offen
    FIXTURE_FREE = "fixture_free"         # Spannvorrichtung frei (kein Werkstück)
    PART_CLAMPED = "part_clamped"         # Werkstück gespannt
    CYCLE_OK = "cycle_ok"                 # Bearbeitung OK / fertig
    LOAD_REQUEST = "load_request"         # Maschine fordert Beladung an
    ROBOT_DONE = "robot_done"             # Roboter meldet Aktion abgeschlossen
