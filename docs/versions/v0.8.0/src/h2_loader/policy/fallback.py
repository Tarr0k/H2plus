"""Fallback-Wrapper: Primary-Policy mit automatischem Fallback.

``FallbackPolicy`` versucht ``primary.predict()``; schlägt das mit einer
beliebigen ``Exception`` fehl (z.B. ``NotImplementedError`` des ``GrootPolicy``-
Stubs), wechselt es automatisch und transparent auf ``fallback.predict()``.

Typisches Muster in ``app.py`` (ADR-0007):

    FallbackPolicy(
        primary=GrootPolicy(...),
        fallback=ScriptedPolicy(poses_dir),
    )

So läuft der GR00T-Pfad schon heute im Kompositions-Root, auch wenn der
echte Checkpoint noch fehlt — dank Fallback auf Teach-&-Replay.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import Action, Observation, PolicyInterface

_log = get_logger(__name__)


class FallbackPolicy(PolicyInterface):
    """Primary-Policy mit automatischem Fallback bei Exception.

    Delegiert ``predict()`` zuerst an ``primary``; bei jeder ``Exception``
    wird die Ausnahme geloggt und ``fallback.predict()`` aufgerufen.

    Args:
        primary:  Zu bevorzugendes Backend (z.B. ``GrootPolicy``).
        fallback: Sicherheits-Backend (z.B. ``ScriptedPolicy``).
    """

    name = "fallback"

    def __init__(self, primary: PolicyInterface, fallback: PolicyInterface) -> None:
        self._primary = primary
        self._fallback = fallback

    def predict(self, obs: Observation) -> Action:
        """Versucht Primary, wechselt bei Fehler auf Fallback.

        Args:
            obs: Beobachtung für ``predict()``.

        Returns:
            Ergebnis von ``primary.predict()`` oder — bei Exception —
            Ergebnis von ``fallback.predict()``.
        """
        try:
            return self._primary.predict(obs)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "FallbackPolicy: Primary-Policy %r fehlgeschlagen (%s: %s) — "
                "wechsle zu Fallback %r.",
                self._primary.name,
                type(exc).__name__,
                exc,
                self._fallback.name,
            )
            return self._fallback.predict(obs)

    def reset(self) -> None:
        """Setzt beide Policies zurück."""
        self._primary.reset()
        self._fallback.reset()
