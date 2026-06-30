"""Gelenk-Clamping-Wrapper für beliebige Inner-Policies.

``SafeguardedPolicy`` klemmt alle Gelenkwinkel in der ``Action``-Ausgabe einer
Inner-Policy auf die konfigurierten ``[lower, upper]``-Grenzen. Notwendig für
nicht-deterministische Policies wie ``GrootPolicy``, aber auch für
``ScriptedPolicy`` als zweite Verteidigungslinie (Defense in Depth).

Das Clamping ist **keine funktionale Sicherheitsmaßnahme** im Sinne von
ISO 13849 — die hardwired Sicherheits-SPS und der ``SafetySupervisor``
(ADR-0005) bleiben zwingend.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import Action, Observation, PolicyInterface

_log = get_logger(__name__)


class SafeguardedPolicy(PolicyInterface):
    """Gelenk-Clamping-Wrapper (Software-Sicherheitsnetz, ADR-0007 §7).

    Delegiert ``predict()`` an die Inner-Policy und klemmt danach jeden
    Gelenkwinkel der zurückgegebenen ``Action`` auf ``[lower[i], upper[i]]``.
    Wird geclamped, erscheint eine Warn-Meldung im Log.

    Wenn der Arm der ``Action`` nicht in ``joint_limits`` vorkommt, wird die
    Action unverändert durchgereicht (Warn-Log).

    Args:
        inner:        Inner-Policy, deren Ausgaben geclamped werden.
        joint_limits: Mapping Armseite -> (lower, upper) je 7 Gelenkwinkel.
    """

    def __init__(
        self,
        inner: PolicyInterface,
        joint_limits: dict[str, tuple[list[float], list[float]]],
    ) -> None:
        self._inner = inner
        self._limits = joint_limits

    @property
    def name(self) -> str:  # type: ignore[override]
        """Dynamischer Name: "safe:<inner.name>"."""
        return f"safe:{self._inner.name}"

    def predict(self, obs: Observation) -> Action:
        """Delegiert an Inner-Policy und klemmt die Gelenkwinkel.

        Args:
            obs: Beobachtung, die unverändert an die Inner-Policy übergeben wird.

        Returns:
            ``Action`` mit gecampten Gelenkwinkeln (oder unverändert, falls
            keine Limits für den Arm konfiguriert sind).
        """
        action = self._inner.predict(obs)

        if action.arm not in self._limits:
            _log.warning(
                "SafeguardedPolicy: Keine Gelenkgrenzen für Arm %r — "
                "Action wird ungeclamped durchgereicht.",
                action.arm,
            )
            return action

        lower, upper = self._limits[action.arm]
        clamped: list[float] = []
        was_clamped = False

        for i, val in enumerate(action.joint_targets):
            lo = lower[i] if i < len(lower) else -float("inf")
            hi = upper[i] if i < len(upper) else float("inf")
            clipped = max(lo, min(hi, val))
            if clipped != val:
                was_clamped = True
            clamped.append(clipped)

        if was_clamped:
            _log.warning(
                "SafeguardedPolicy: Gelenkwinkel geclamped (arm=%s, original=%s, clamped=%s)",
                action.arm,
                action.joint_targets,
                clamped,
            )

        return Action(
            arm=action.arm,
            joint_targets=clamped,
            gripper_closed=action.gripper_closed,
        )

    def reset(self) -> None:
        """Setzt den Zustand der Inner-Policy zurück."""
        self._inner.reset()
