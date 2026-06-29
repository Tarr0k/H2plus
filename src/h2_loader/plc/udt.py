"""Python-Spiegel der TIA-UDT ``H2Interface_UDT``.

Einzige Quelle der Wahrheit für alle UDT-Member und die NodeId-Konstruktion.
Auf dem Zielsystem wird ``node_id()`` genutzt, um OPC-UA-Nodes zu adressieren;
hier (In-Memory-Stub) dient es als Schlüssel im Zustandsspeicher.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

IFACE_ROOT = "iface"
"""Wurzel-Member der UDT innerhalb des Interface-DBs."""


# ---------------------------------------------------------------------------
# Feldkatalog
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Field:
    """Ein UDT-Member mit Sektion, Name und Datentyp (TIA-Schreibweise)."""

    section: str
    name: str
    dtype: str


#: Alle 41 Member der H2Interface_UDT als geordnetes Tupel.
FIELDS: tuple[Field, ...] = (
    # --- control (7) ---
    Field("control", "interfaceVersion",  "UInt"),
    Field("control", "plcHeartbeat",      "UInt"),
    Field("control", "robotHeartbeat",    "UInt"),
    Field("control", "plcAlive",          "Bool"),
    Field("control", "robotAlive",        "Bool"),
    Field("control", "robotConnected",    "Bool"),
    Field("control", "operatingMode",     "Int"),
    # --- plcToRobot (13) ---
    Field("plcToRobot", "jobRequest",         "Int"),
    Field("plcToRobot", "jobId",              "DInt"),
    Field("plcToRobot", "partType",           "Int"),
    Field("plcToRobot", "jobReqToggle",       "Bool"),
    Field("plcToRobot", "machineReady",       "Bool"),
    Field("plcToRobot", "doorOpen",           "Bool"),
    Field("plcToRobot", "doorClosed",         "Bool"),
    Field("plcToRobot", "clampOpen",          "Bool"),
    Field("plcToRobot", "clampClosed",        "Bool"),
    Field("plcToRobot", "machineCycleRun",    "Bool"),
    Field("plcToRobot", "machineFault",       "Bool"),
    Field("plcToRobot", "zoneFreeForRobot",   "Bool"),
    Field("plcToRobot", "partInClamp",        "Bool"),
    # --- robotToPlc (16) ---
    Field("robotToPlc", "robotState",       "Int"),
    Field("robotToPlc", "jobIdEcho",        "DInt"),
    Field("robotToPlc", "jobAckToggle",     "Bool"),
    Field("robotToPlc", "jobDoneToggle",    "Bool"),
    Field("robotToPlc", "jobResult",        "Int"),
    Field("robotToPlc", "currentStep",      "Int"),
    Field("robotToPlc", "reqOpenDoor",      "Bool"),
    Field("robotToPlc", "reqCloseDoor",     "Bool"),
    Field("robotToPlc", "reqOpenClamp",     "Bool"),
    Field("robotToPlc", "reqCloseClamp",    "Bool"),
    Field("robotToPlc", "robotReady",       "Bool"),
    Field("robotToPlc", "robotBusy",        "Bool"),
    Field("robotToPlc", "gripperHoldsPart", "Bool"),
    Field("robotToPlc", "robotInMachine",   "Bool"),
    Field("robotToPlc", "errorActive",      "Bool"),
    Field("robotToPlc", "errorCode",        "DInt"),
    # --- safety (5) ---
    Field("safety", "estopFromPlc",    "Bool"),
    Field("safety", "estopFromRobot",  "Bool"),
    Field("safety", "safeZoneClear",   "Bool"),
    Field("safety", "robotEnable",     "Bool"),
    Field("safety", "watchdogFault",   "Bool"),
)


# ---------------------------------------------------------------------------
# Kodierte Werte
# ---------------------------------------------------------------------------

class JobRequest(IntEnum):
    """Auftragsart (plcToRobot.jobRequest)."""

    NONE             = 0
    LOAD             = 1
    UNLOAD           = 2
    CHANGE_INDUCTOR  = 3


class RobotState(IntEnum):
    """Roboter-Zustand (robotToPlc.robotState)."""

    INIT      = 0
    IDLE      = 1
    BUSY      = 2
    DONE      = 3
    ERROR     = 4
    NOT_READY = 5


class JobResult(IntEnum):
    """Ergebnis des letzten Auftrags (robotToPlc.jobResult)."""

    OPEN = 0   # Noch kein Ergebnis / offen
    OK   = 1
    NOK  = 2


class OperatingMode(IntEnum):
    """Betriebsmodus (control.operatingMode)."""

    OFF    = 0
    MANUAL = 1
    AUTO   = 2
    SETUP  = 3


# ---------------------------------------------------------------------------
# NodeId-Konstruktor
# ---------------------------------------------------------------------------

def node_id(db_name: str, section: str, member: str, ns: int = 3) -> str:
    """Baut den OPC-UA-NodeId-String für einen UDT-Member.

    Format::

        ns=3;s="H2_Interface_DB"."iface"."control"."plcHeartbeat"

    Args:
        db_name: Name des TIA-Datenbausteins (z. B. ``"H2_Interface_DB"``).
        section: Sektion innerhalb des IFACE_ROOT-Members (z. B. ``"control"``).
        member:  Membername in der Sektion (z. B. ``"plcHeartbeat"``).
        ns:      OPC-UA-Namespace-Index (Standard: 3).

    Returns:
        Vollständiger NodeId-String.
    """
    return f'ns={ns};s="{db_name}"."{IFACE_ROOT}"."{section}"."{member}"'
