"""OPC-UA-Transport für den H2-Handshake via asyncua.

Verbindet sich mit einem S7-1500 OPC-UA-Server und liest/schreibt die
UDT-Member über String-NodeIds nach dem TIA-Schema:

    ns=3;s="H2_Interface_DB"."iface"."<section>"."<member>"

asyncua wird per Lazy-Import in ``connect()`` geladen, damit das Paket
auch ohne installiertes asyncua importierbar bleibt (Default-Suite
läuft ohne diese Abhängigkeit durch).

Auf der realen SPS muss der Datenbaustein ``H2_Interface_DB`` in den
OPC-UA-Servereinstellungen als erreichbar freigeschaltet sein.
"""

from __future__ import annotations

from ..util.logging import get_logger
from . import udt
from .transport import HandshakeTransport

_log = get_logger(__name__)

# Mapping TIA-Datentyp → ua.VariantType (wird in connect() befüllt, sobald
# ua importiert werden konnte).
_DTYPE_TO_VARIANT: dict[str, object] = {}


class AsyncuaTransport(HandshakeTransport):
    """OPC-UA-Transport auf Basis von asyncua.sync.Client.

    Nutzt die synchrone asyncua-API, sodass keine asyncio-Eventloop im
    aufrufenden Code nötig ist. Der Client wird in ``connect()`` geöffnet
    und in ``disconnect()`` wieder geschlossen.

    NodeId-Schema (S7-1500 TIA V17+)::

        ns=3;s="H2_Interface_DB"."iface"."control"."plcHeartbeat"

    ua-Typ-Zuordnung:
    - Bool  → ua.VariantType.Boolean
    - Int   → ua.VariantType.Int16
    - UInt  → ua.VariantType.UInt16
    - DInt  → ua.VariantType.Int32

    Args:
        endpoint: OPC-UA-Endpunkt-URL (z. B. ``"opc.tcp://192.168.100.1:4840"``).
        db_name:  Name des TIA-Interface-DBs (Standard: ``"H2_Interface_DB"``).
        ns:       OPC-UA-Namespace-Index (Standard: 3).
    """

    def __init__(
        self,
        endpoint: str,
        db_name: str = "H2_Interface_DB",
        ns: int = 3,
    ) -> None:
        self._endpoint = endpoint
        self._db_name = db_name
        self._ns = ns
        self._client: object | None = None
        # Vorberechnetes Dtype-Lookup: (section, member) → dtype
        self._dtypes: dict[tuple[str, str], str] = {
            (f.section, f.name): f.dtype for f in udt.FIELDS
        }

    # ------------------------------------------------------------------
    # Verbindungsmanagement
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Öffnet die OPC-UA-Verbindung (Lazy-Import von asyncua)."""
        from asyncua.sync import Client  # noqa: PLC0415  # Lazy-Import bewusst
        from asyncua import ua  # noqa: PLC0415

        # Typ-Map jetzt befüllen, da ua erst hier verfügbar ist
        global _DTYPE_TO_VARIANT
        if not _DTYPE_TO_VARIANT:
            _DTYPE_TO_VARIANT = {
                "Bool": ua.VariantType.Boolean,
                "Int":  ua.VariantType.Int16,
                "UInt": ua.VariantType.UInt16,
                "DInt": ua.VariantType.Int32,
            }

        _log.info("AsyncuaTransport.connect: %s", self._endpoint)
        client = Client(self._endpoint)
        client.connect()
        self._client = client

    def disconnect(self) -> None:
        """Schließt die OPC-UA-Verbindung (fehlertolerant)."""
        if self._client is None:
            return
        try:
            self._client.disconnect()  # type: ignore[union-attr]
            _log.info("AsyncuaTransport.disconnect: getrennt")
        except Exception as exc:  # noqa: BLE001
            _log.warning("AsyncuaTransport.disconnect: Fehler ignoriert: %s", exc)
        finally:
            self._client = None

    # ------------------------------------------------------------------
    # Lesen / Schreiben
    # ------------------------------------------------------------------

    def read(self, section: str, member: str) -> int | bool:
        """Liest einen UDT-Member via OPC-UA.

        Args:
            section: Sektion (z. B. ``"control"``).
            member:  Membername.

        Returns:
            Aktueller Wert vom OPC-UA-Server.
        """
        if self._client is None:
            raise RuntimeError("AsyncuaTransport: nicht verbunden (connect() fehlt)")
        nid = udt.node_id(self._db_name, section, member, self._ns)
        value: int | bool = self._client.get_node(nid).read_value()  # type: ignore[union-attr]
        _log.debug("read  %s = %r", nid, value)
        return value

    def write(self, section: str, member: str, value: int | bool) -> None:
        """Schreibt einen UDT-Member via OPC-UA mit korrektem ua-Typ.

        Args:
            section: Sektion.
            member:  Membername.
            value:   Neuer Wert.
        """
        if self._client is None:
            raise RuntimeError("AsyncuaTransport: nicht verbunden (connect() fehlt)")

        from asyncua import ua  # noqa: PLC0415  # ua muss hier verfügbar sein

        nid = udt.node_id(self._db_name, section, member, self._ns)
        node = self._client.get_node(nid)  # type: ignore[union-attr]

        dtype = self._dtypes.get((section, member))
        if dtype is None:
            _log.warning(
                "AsyncuaTransport.write: Unbekannter Member %s.%s — schreibe ohne expliziten Typ",
                section,
                member,
            )
            node.write_value(ua.Variant(value))
        else:
            vtype = _DTYPE_TO_VARIANT[dtype]
            node.write_value(ua.DataValue(ua.Variant(value, vtype)))

        _log.debug("write %s = %r", nid, value)
