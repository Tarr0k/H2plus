"""Strukturiertes Logging für h2_loader.

Bewusst dünn gehalten: ein einziger Konfigurationspunkt, damit alle Module über
``get_logger(__name__)`` einheitlich loggen. Auf dem Zielsystem kann hier später
ein JSON-Handler oder eine Anbindung an die Maschinen-Diagnose ergänzt werden,
ohne dass aufrufende Module sich ändern.
"""

from __future__ import annotations

import logging

_CONFIGURED = False

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Initialisiert das Root-Logging einmalig (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(level=level, format=_DEFAULT_FORMAT)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Liefert einen benannten Logger; stellt sicher, dass Logging konfiguriert ist."""
    configure_logging()
    return logging.getLogger(name)
