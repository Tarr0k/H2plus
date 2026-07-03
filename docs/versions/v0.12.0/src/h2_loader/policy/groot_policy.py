"""GR00T N1.7 Policy-Adapter (Ein-/Ausgabe-Mapping fertig, Inferenz noch offen).

Dokumentiert und implementiert den geplanten Ablauf für die GR00T-Integration:
- Modell: ``nvidia/GR00T-N1.7-3B`` (~3B Parameter, Apache-2.0, auf HuggingFace)
- H2 als ``NEW_EMBODIMENT``: eigenes Fine-Tuning nötig (URDF, Modality-Config,
  Teleop-Datenerfassung mit ``xr_teleoperate``); Modality-Config siehe
  ``groot/h2_modality_config.py``.
- Inferenz: TensorRT auf Jetson AGX Thor (~10,7 Hz, ~93 ms Latenz)
- Sicherheit: Safety-Clamping via ``SafeguardedPolicy`` VOR dem Arm-SDK

Stand dieser Datei (v0.12.0): Das **Ein-/Ausgabe-Mapping** zwischen unserer
``Observation``/``Action`` und dem GR00T-Eingabe-/Ausgabeformat ist fertig
(``_observation_to_groot`` / ``_groot_action_to_action``). Es fehlt nur noch
die **Modell-Inferenz selbst** — die läuft ausschließlich auf dem Training-/
Deployment-Rig (Linux + CUDA) und ist hier bewusst nicht nachgebildet.

Realer Ablauf (sobald die Inferenz ergänzt ist):
    1. GR00T-Checkpoint laden (TensorRT-optimiert für AGX Thor).
    2. ``predict()``: ``_observation_to_groot()`` aufrufen → RGB-Bilder +
       Propriozeption normalisieren → GR00T-Encoder → Diffusion-Policy-Decoder
       → Gelenkwinkel-Trajektorie (200 ms) → ersten Schritt extrahieren →
       via ``_groot_action_to_action()`` in ``Action`` zurückwandeln.
    3. ``reset()``: RNN-Hidden-States zurücksetzen (Episode-Grenze).

Deployment-Hardware: Jetson AGX Thor (128 GB shared; TensorRT ~10,7 Hz).
Fallback:           ``FallbackPolicy(GrootPolicy(...), ScriptedPolicy(...))``.
Dokumentation:      ``docs/roadmap_groot.md``, ``docs/groot_setup.md``, ADR-0007.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..util.logging import get_logger
from .base import Action, Observation, PolicyInterface

_log = get_logger(__name__)


class GrootPolicy(PolicyInterface):
    """GR00T N1.7 Policy — Ein-/Ausgabe-Mapping fertig, Inferenz noch offen.

    Dokumentiert und implementiert den Zielzustand gemäß ADR-0007, so weit es
    ohne installiertes ``gr00t``-Paket und ohne GPU möglich ist: Die
    Übersetzung zwischen unserer ``Observation``/``Action`` und dem
    GR00T-Ein-/Ausgabeformat steht (``_observation_to_groot`` /
    ``_groot_action_to_action``). ``predict()`` wirft weiterhin
    ``NotImplementedError``, da die eigentliche Modell-Inferenz nur auf dem
    Training-/Deployment-Rig (Linux + CUDA) läuft.

    Realer Ablauf nach Ergänzung der Inferenz:
        - Embodiment: H2 EDU als ``NEW_EMBODIMENT`` (Fine-Tuning erforderlich).
        - Training: GR00T-flavored LeRobot v2 Datensatz (Teleop-Demos), siehe
          ``h2_loader.dataset.LerobotDatasetExporter``.
        - Inferenz: TensorRT auf Jetson AGX Thor (~10,7 Hz mit ~93 ms Latenz).
        - Safety: ``SafeguardedPolicy`` klemmt alle Ausgaben vor dem Arm-SDK.

    Args:
        embodiment_tag: Embodiment-Kennung (Default: "new_embodiment" für H2).
        checkpoint:     HuggingFace-Modell-ID oder lokaler Pfad des Checkpoints.
        model_path:     Optionaler lokaler Override (z.B. TensorRT-Engine-Pfad).
        arm:            Armseite, für die Aktionen erzeugt werden ("right").
    """

    name = "groot"

    #: H2-Armgelenke 22-28 (rechter Arm), Reihenfolge wie in ``state.right_arm``
    #: / ``action.right_arm`` der Modality-Config (siehe ``docs/sdk_reference.md``).
    H2_RIGHT_ARM_JOINTS: tuple[str, ...] = (
        "RightShoulderPitch",
        "RightShoulderRoll",
        "RightShoulderYaw",
        "RightElbow",
        "RightWristRoll",
        "RightWristPitch",
        "RightWristYaw",
    )

    def __init__(
        self,
        embodiment_tag: str = "new_embodiment",
        checkpoint: str = "nvidia/GR00T-N1.7-3B",
        model_path: str | None = None,
        arm: str = "right",
    ) -> None:
        self._embodiment_tag = embodiment_tag
        self._checkpoint = checkpoint
        self._model_path = model_path
        self._arm = arm
        _log.info(
            "GrootPolicy: initialisiert (embodiment=%s, checkpoint=%s, arm=%s)",
            embodiment_tag,
            checkpoint,
            arm,
        )

    def _observation_to_groot(self, obs: Observation) -> dict[str, object]:
        """Baut das GR00T-Eingabe-Dict aus einer ``Observation``.

        Die Schlüssel entsprechen den Modality-Keys aus
        ``groot/h2_modality_config.py`` (``video.*``, ``state.*``,
        ``annotation.human.task_description``). Fehlt der Gelenkzustand des
        gewählten Arms, wird mit Nullen aufgefüllt statt einen Fehler zu werfen
        (die Beobachtung kann z.B. beim allerersten Schritt unvollständig sein).

        Args:
            obs: Aktuelle Beobachtung (Ziel, Gelenkzustand, Kamerabilder).

        Returns:
            Dict im GR00T-Eingabeformat (Bilder als Platzhalter/None erlaubt).
        """
        joint_state = (obs.joint_state or {}).get(self._arm)
        right_arm = list(joint_state) if joint_state else [0.0] * len(self.H2_RIGHT_ARM_JOINTS)
        images = obs.images or {}
        return {
            "video.head": images.get("head"),
            "video.wrist": images.get("wrist"),
            "state.right_arm": right_arm,
            "state.gripper": [0.0],
            "annotation.human.task_description": obs.goal or "",
        }

    def _groot_action_to_action(self, groot_action: Sequence[float]) -> Action:
        """Wandelt einen GR00T-Action-Vektor in unsere ``Action`` um.

        Erwartet die 7 ``right_arm``-Gelenkwinkel, optional gefolgt von einem
        8. Wert für den Greifer (Schwelle 0.5: >= 0.5 → geschlossen).

        Args:
            groot_action: Sequenz von 7 (oder 8, mit Greifer) Gleitkommawerten.

        Returns:
            ``Action`` mit den 7 Gelenkwinkeln für ``self._arm`` und optionalem
            Greifer-Sollzustand.

        Raises:
            ValueError: wenn ``groot_action`` weder 7 noch 8 Werte enthält.
        """
        n_joints = len(self.H2_RIGHT_ARM_JOINTS)
        n = len(groot_action)
        if n not in (n_joints, n_joints + 1):
            _log.error(
                "GrootPolicy: unerwartete Länge des GR00T-Action-Vektors: %d (erwartet %d oder %d)",
                n,
                n_joints,
                n_joints + 1,
            )
            raise ValueError(
                f"GrootPolicy: erwartet {n_joints} oder {n_joints + 1} Werte "
                f"(right_arm [+ gripper]), erhielt {n}"
            )
        joint_targets = list(groot_action[:n_joints])
        gripper_closed = groot_action[n_joints] >= 0.5 if n == n_joints + 1 else None
        return Action(arm=self._arm, joint_targets=joint_targets, gripper_closed=gripper_closed)

    def predict(self, obs: Observation) -> Action:
        """Baut das GR00T-Eingabe-Mapping auf, wirft dann ``NotImplementedError``.

        Das Ein-/Ausgabe-Mapping (``_observation_to_groot`` /
        ``_groot_action_to_action``) ist fertig; es fehlt nur die eigentliche
        Modell-Inferenz, die ausschließlich auf dem Training-/Deployment-Rig
        (Linux + CUDA) läuft. Im Produktionsbetrieb wird dieser Aufruf über
        ``FallbackPolicy`` an ``ScriptedPolicy`` weitergeleitet.

        Args:
            obs: Aktuelle Beobachtung (Ziel, Gelenkzustand, Kamerabilder).

        Raises:
            NotImplementedError: immer, bis die Modell-Inferenz ergänzt ist.
        """
        groot_input = self._observation_to_groot(obs)
        _log.debug("GrootPolicy: GR00T-Eingabe-Mapping erzeugt (keys=%s)", list(groot_input))
        raise NotImplementedError(
            "GR00T-Inferenz: Modell laden + inferieren auf dem Rig (Linux+CUDA, "
            "nvidia/GR00T-N1.7-3B); Mapping via _groot_action_to_action steht "
            "bereit. Siehe docs/groot_setup.md"
        )
