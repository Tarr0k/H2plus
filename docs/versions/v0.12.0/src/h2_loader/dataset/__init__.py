"""Dataset-Paket: Export von Policy-Trainingsdaten ins GR00T-flavored LeRobot-v2-Format.

Bereitet die Artefakte für das spätere GR00T-Fine-Tuning vor (ADR-0007,
Stufe 1/2): ``LerobotDatasetExporter`` schreibt Observation/Action-Schritte
aus Teleop- oder Simulationsläufen in ein Verzeichnis-Layout, das sich auf dem
Training-Rig zu einem vollständigen LeRobot-v2-Datensatz erweitern lässt.

Verfügbare Klassen:
    - ``LerobotDatasetExporter``: Episoden-/Meta-Export (dependency-light).
"""

from .lerobot_export import LerobotDatasetExporter

__all__ = ["LerobotDatasetExporter"]
