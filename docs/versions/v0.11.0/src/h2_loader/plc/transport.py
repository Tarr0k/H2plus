"""Abstrakte Transport-Schnittstelle für den H2-Handshake.

Trennt die Handshake-Logik vom konkreten Kommunikations-Backend.
Der Standard-Backend (In-Memory) verbleibt im ``H2HandshakeClient`` selbst
und eignet sich für Sim/Test ohne externe Abhängigkeiten.
Für das Zielsystem (S7-1500 via OPC-UA) steht ``AsyncuaTransport`` bereit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class HandshakeTransport(ABC):
    """Abstrakter Lese-/Schreib-Kanal des H2-Handshakes.

    Implementierungen:
    - In-Memory (Sim/Test): verbleibt direkt im ``H2HandshakeClient``
      (kein eigenes Transport-Objekt nötig).
    - OPC-UA (Zielsystem): ``AsyncuaTransport`` aus ``asyncua_transport.py``.

    Ein Transport wird durch Übergabe an ``H2HandshakeClient(transport=...)``
    aktiviert. Danach delegieren alle ``read``/``write``-Aufrufe des Clients
    transparent an diesen Transport.
    """

    @abstractmethod
    def connect(self) -> None:
        """Baut die Verbindung zum Kommunikations-Backend auf."""

    @abstractmethod
    def disconnect(self) -> None:
        """Schließt die Verbindung (fehlertolerant implementieren)."""

    @abstractmethod
    def read(self, section: str, member: str) -> int | bool:
        """Liest einen UDT-Member vom Backend.

        Args:
            section: Sektion (z. B. ``"control"``).
            member:  Membername (z. B. ``"plcHeartbeat"``).

        Returns:
            Aktueller Wert (int oder bool).
        """

    @abstractmethod
    def write(self, section: str, member: str, value: int | bool) -> None:
        """Schreibt einen UDT-Member ins Backend.

        Args:
            section: Sektion.
            member:  Membername.
            value:   Neuer Wert.
        """
