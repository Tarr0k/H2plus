"""Sicherheits-/Freigabelogik (Stub).

Bündelt Not-Aus und Freigabe. In dieser Ausbaustufe ein Gerüst: die echte
Sicherheit liegt im SPS-Sicherheitskreis (zweikanalig, zertifiziert) und NICHT
in dieser Software. ``SafetyGate`` dient nur dazu, im Ablauf eine prüfbare
Freigabe-Bedingung zu haben, bevor ein Skill Aktorik bewegt.
"""

from __future__ import annotations

from ..util.logging import get_logger

_log = get_logger(__name__)


class SafetyGate:
    """Software-seitige Freigabe vor Bewegungsaktionen (kein Ersatz für den SPS-Sicherheitskreis)."""

    def __init__(self) -> None:
        self._emergency_stop = False

    def trigger_emergency_stop(self) -> None:
        _log.error("SafetyGate: NOT-AUS ausgelöst")
        self._emergency_stop = True

    def reset(self) -> None:
        _log.info("SafetyGate: zurückgesetzt")
        self._emergency_stop = False

    def is_clear(self) -> bool:
        """True, wenn keine Sicherheitsverriegelung aktiv ist."""
        return not self._emergency_stop
