"""Abstrakte Basis des Policy-Seams (ADR-0007).

``PolicyInterface`` ist die austauschbare Manipulations-Policy hinter der
Skill-Ebene. Heute liefert ``ScriptedPolicy`` die Bewegung durch deterministische
Teach-in-Posen; in Stufe 3 übernimmt ``GrootPolicy`` mit GR00T N1.7-Inferenz.

Backends:
    - ``ScriptedPolicy``: Teach-&-Replay als Policy (Fallback, deterministisch).
    - ``GrootPolicy``:    GR00T N1.7 Fine-Tuned für H2 NEW_EMBODIMENT (Zielzustand).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Observation:
    """Eingabe für ``PolicyInterface.predict()``.

    Attributes:
        goal:        Symbolisches Ziel der Aktion (z.B. Posename "load_workpiece").
        joint_state: Aktuelle Gelenkwinkel je Armseite (Propriozeption).
        images:      RGB-Bilder je Kamera-ID (Platzhalter; für GR00T-Inferenz).
    """

    goal: str | None = None
    joint_state: dict[str, list[float]] | None = None
    images: dict[str, object] | None = None


@dataclass
class Action:
    """Ausgabe von ``PolicyInterface.predict()``.

    Attributes:
        arm:            Armseite ("left" oder "right"), die bewegt werden soll.
        joint_targets:  Soll-Gelenkwinkel [rad] für alle 7 DoF des Arms.
        gripper_closed: Greifer-Sollzustand; None bedeutet "unverändert lassen".
    """

    arm: str
    joint_targets: list[float]
    gripper_closed: bool | None = field(default=None)


class PolicyInterface(ABC):
    """Abstrakte Manipulations-Policy (ADR-0007).

    Jedes Backend implementiert ``predict()`` und bekommt eine ``Observation``
    als Eingabe (Ziel + Sensorik). Die Ausgabe ist eine ``Action`` mit den
    nächsten Soll-Gelenkwinkeln für einen Arm.

    Backends:
        - ``ScriptedPolicy``: deterministisch, Teach-in als Policy (heute).
        - ``GrootPolicy``:    GR00T N1.7-Inferenz auf Jetson Thor (Zielzustand).

    Der Composition Root (``app.py``) wählt das Backend und verpackt es
    optional in ``SafeguardedPolicy`` (Clamping) und ``FallbackPolicy``.
    """

    name: str = "policy"

    @abstractmethod
    def predict(self, obs: Observation) -> Action:
        """Liefert die nächste Arm-Aktion für die gegebene Beobachtung.

        Args:
            obs: Aktuelle Beobachtung (Ziel, Gelenkzustand, Kamerabilder).

        Returns:
            ``Action`` mit Soll-Gelenkwinkeln und optionalem Greifer-Zustand.
        """

    def reset(self) -> None:
        """Setzt internen Zustand zurück (z.B. RNN-Hidden-States bei GR00T).

        Standard-Implementierung ist ein No-op (stateless Policies).
        """
