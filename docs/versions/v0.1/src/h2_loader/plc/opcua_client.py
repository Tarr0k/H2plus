"""OPC-UA-Anbindung an die Maschinen-SPS (Stub).

Implementiert ``PlcInterface`` über ``python-opcua`` (Extra ``[plc]``). Hier nur
Gerüst: ein In-Memory-Signalspeicher, damit der Ablauf ohne reale SPS testbar
ist. Der OPC-UA-Client wird lazy verbunden; das Signal-Mapping
(Name -> NodeId) kommt aus ``config/plc.yaml``.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import PlcInterface
from .signals import Signal

_log = get_logger(__name__)


class OpcUaPlcClient(PlcInterface):
    """OPC-UA-SPS-Client (Stub) mit In-Memory-Signalspeicher.

    Args:
        endpoint: OPC-UA Endpunkt-URL (z. B. opc.tcp://host:4840).
        node_map: Mapping Signal-Name -> NodeId-String (aus config/plc.yaml).
    """

    def __init__(self, endpoint: str = "", node_map: dict[str, str] | None = None) -> None:
        self._endpoint = endpoint
        self._node_map = node_map or {}
        self._state: dict[Signal, bool] = {}
        self._connected = False

    def connect(self) -> None:
        _log.info("OpcUaPlcClient: connect %s (Stub)", self._endpoint)
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def read_signal(self, signal: Signal) -> bool:
        return self._state.get(signal, False)

    def write_signal(self, signal: Signal, value: bool) -> None:
        _log.info("OpcUaPlcClient: write %s = %s (Stub)", signal.value, value)
        self._state[signal] = value

    def wait_for(self, signal: Signal, value: bool = True, timeout_s: float | None = None) -> bool:
        # Stub: kein Blockieren/Polling. Auf dem Zielsystem hier OPC-UA-Subscription
        # oder gepolltes Lesen bis timeout_s.
        _log.info("OpcUaPlcClient: wait_for %s == %s (Stub, sofortige Rückgabe)", signal.value, value)
        return self._state.get(signal, False) == value
