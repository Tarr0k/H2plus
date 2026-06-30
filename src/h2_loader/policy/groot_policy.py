"""GR00T N1.7 Policy-Stub (Zielzustand, noch nicht implementiert).

Dieser Stub dokumentiert den geplanten Ablauf für die GR00T-Integration:
- Modell: ``nvidia/GR00T-N1.7-3B`` (~3B Parameter, Apache-2.0, auf HuggingFace)
- H2 als ``NEW_EMBODIMENT``: eigenes Fine-Tuning nötig (URDF, Modality-Config,
  Teleop-Datenerfassung mit ``xr_teleoperate``)
- Inferenz: TensorRT auf Jetson AGX Thor (~10,7 Hz, ~93 ms Latenz)
- Sicherheit: Safety-Clamping via ``SafeguardedPolicy`` VOR dem Arm-SDK

Realer Ablauf (sobald Stufe 3 abgeschlossen):
    1. GR00T-Checkpoint laden (TensorRT-optimiert für AGX Thor).
    2. ``predict()``: RGB-Bilder + Propriozeption normalisieren → GR00T-Encoder
       → Diffusion-Policy-Decoder → Gelenkwinkel-Trajektorie (200 ms) → ersten
       Schritt extrahieren → als ``Action`` zurückgeben.
    3. ``reset()``: RNN-Hidden-States zurücksetzen (Episode-Grenze).

Deployment-Hardware: Jetson AGX Thor (128 GB shared; TensorRT ~10,7 Hz).
Fallback:           ``FallbackPolicy(GrootPolicy(...), ScriptedPolicy(...))``.
Dokumentation:      ``docs/roadmap_groot.md``, ADR-0007.
"""

from __future__ import annotations

from ..util.logging import get_logger
from .base import Action, Observation, PolicyInterface

_log = get_logger(__name__)


class GrootPolicy(PolicyInterface):
    """GR00T N1.7 Policy — Stub für zukünftige Implementierung.

    Dokumentiert den Zielzustand gemäß ADR-0007. Wirft ``NotImplementedError``
    bis Stufe 3 (Deployment auf Jetson Thor) abgeschlossen ist.

    Realer Ablauf nach Implementierung:
        - Embodiment: H2 EDU als ``NEW_EMBODIMENT`` (Fine-Tuning erforderlich).
        - Training: GR00T-flavored LeRobot v2 Datensatz (Teleop-Demos).
        - Inferenz: TensorRT auf Jetson AGX Thor (~10,7 Hz mit ~93 ms Latenz).
        - Safety: ``SafeguardedPolicy`` klemmt alle Ausgaben vor dem Arm-SDK.

    Args:
        embodiment_tag: Embodiment-Kennung (Default: "new_embodiment" für H2).
        checkpoint:     HuggingFace-Modell-ID oder lokaler Pfad des Checkpoints.
        model_path:     Optionaler lokaler Override (z.B. TensorRT-Engine-Pfad).
    """

    name = "groot"

    def __init__(
        self,
        embodiment_tag: str = "new_embodiment",
        checkpoint: str = "nvidia/GR00T-N1.7-3B",
        model_path: str | None = None,
    ) -> None:
        self._embodiment_tag = embodiment_tag
        self._checkpoint = checkpoint
        self._model_path = model_path
        _log.info(
            "GrootPolicy: Stub initialisiert (embodiment=%s, checkpoint=%s)",
            embodiment_tag,
            checkpoint,
        )

    def predict(self, obs: Observation) -> Action:  # noqa: ARG002
        """Nicht implementiert — wirft ``NotImplementedError``.

        Wird in Stufe 3 durch echte GR00T N1.7-Inferenz ersetzt.
        Im Produktionsbetrieb über ``FallbackPolicy`` an ``ScriptedPolicy``
        weitergeleitet, bis der Checkpoint vorliegt.

        Args:
            obs: Aktuelle Beobachtung (wird ignoriert, da noch kein Modell).

        Raises:
            NotImplementedError: immer, bis Stufe 3 abgeschlossen ist.
        """
        raise NotImplementedError(
            "GR00T-Inferenz folgt — H2 als NEW_EMBODIMENT, "
            "Deployment auf Jetson Thor; siehe docs/roadmap_groot.md"
        )
