"""H2 NEW_EMBODIMENT Modality-Config für GR00T N1.7 (ADR-0007, Zielarchitektur).

Nur auf dem Training-Rig mit installiertem ``gr00t``-Paket verwendbar
(Linux + CUDA; hier nicht ausführbar). Diese Datei liegt bewusst außerhalb von
``src/`` und wird von der Testsuite NICHT importiert, da ``gr00t`` in diesem
Repo nicht installiert ist.

Aufbau nach dem Muster ``examples/SO100/so100_config.py`` aus
github.com/NVIDIA/Isaac-GR00T: eine Modality-Config ist ein Dict mit den
Schlüsseln ``"video"``, ``"state"``, ``"action"`` und ``"language"``, das über
``register_modality_config(..., embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)``
für das H2-Embodiment registriert wird.

H2-Armgelenke 22-28 (rechter Arm, siehe ``docs/sdk_reference.md``):
    RightShoulderPitch, RightShoulderRoll, RightShoulderYaw, RightElbow,
    RightWristRoll, RightWristPitch, RightWristYaw.

Die physische Struktur, auf die diese Config verweist (Gelenk-Indizes je
Modality-Key), steht in ``groot/meta_modality.example.json`` und wird von
``h2_loader.dataset.LerobotDatasetExporter`` erzeugt. Details siehe
``docs/groot_setup.md`` und ``docs/roadmap_groot.md``.
"""

from __future__ import annotations

from gr00t.configs.data.embodiment_configs import register_modality_config
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.data.types import (
    ActionConfig,
    ActionFormat,
    ActionRepresentation,
    ActionType,
    ModalityConfig,
)

#: Modality-Config für den H2-Lader als NEW_EMBODIMENT.
#: - video:    Kopf-Binokular ("head") + rechtes Handgelenk ("wrist").
#: - state:    Propriozeption des rechten Arms (7 DoF) + Greifer (1 DoF).
#: - action:   16-Schritt-Vorhersagehorizont für Arm (relativ) + Greifer (absolut).
#: - language: Aufgabenbeschreibung als natürlichsprachige Annotation.
h2_config = {
    "video": ModalityConfig(
        delta_indices=[0],
        modality_keys=["head", "wrist"],
    ),
    "state": ModalityConfig(
        delta_indices=[0],
        modality_keys=["right_arm", "gripper"],
    ),
    "action": ModalityConfig(
        delta_indices=list(range(0, 16)),
        modality_keys=["right_arm", "gripper"],
        action_configs={
            "right_arm": ActionConfig(
                rep=ActionRepresentation.RELATIVE,
                type=ActionType.NON_EEF,
                format=ActionFormat.DEFAULT,
            ),
            "gripper": ActionConfig(
                rep=ActionRepresentation.ABSOLUTE,
                type=ActionType.NON_EEF,
                format=ActionFormat.DEFAULT,
            ),
        },
    ),
    "language": ModalityConfig(
        delta_indices=[0],
        modality_keys=["annotation.human.task_description"],
    ),
}

register_modality_config(h2_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
