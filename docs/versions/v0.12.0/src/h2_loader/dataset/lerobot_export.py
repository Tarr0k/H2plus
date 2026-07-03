"""GR00T-flavored LeRobot-v2-Export-Gerüst (ADR-0007, Stufe 1/2).

Dies ist das GERÜST für den Trainingsdaten-Export: Es schreibt die korrekte
Verzeichnis-/Meta-Struktur eines GR00T-flavored LeRobot-v2-Datensatzes
(``meta/modality.json``, ``meta/info.json``, ``meta/episodes.jsonl``,
``meta/tasks.jsonl``, ``data/chunk-000/episode_<N>.jsonl``) — portabel und
dependency-light (stdlib ``json``, kein Pflicht-``pyarrow``).

Die echte LeRobot-v2-Nutzung (Parquet-Episodendateien + H.264-mp4 via
``torchcodec``) erfolgt erst auf dem Training-Rig; hier liefert der Exporter
dafür nur JSONL-Platzhalter (zusätzlich Parquet, falls ``pyarrow`` installiert
ist). Videos werden von diesem Exporter NICHT erzeugt.

Exportiert wird heute nur der rechte Arm (H2JointIndex 22-28, siehe
``docs/sdk_reference.md``); die Modality-Struktur entspricht
``groot/h2_modality_config.py`` / ``groot/meta_modality.example.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..policy.base import Action, Observation
from ..util.logging import get_logger

_log = get_logger(__name__)

try:
    import pyarrow  # noqa: F401
except ImportError:
    _HAS_PYARROW = False
else:
    _HAS_PYARROW = True


class LerobotDatasetExporter:
    """Schreibt Observation/Action-Schritte ins GR00T-flavored LeRobot-v2-Layout.

    Nutzung::

        exporter = LerobotDatasetExporter(out_dir, fps=30, arm="right")
        exporter.start_episode("load_workpiece")
        for obs, action in demo:
            exporter.add_step(obs, action)
        exporter.end_episode()
        # ... weitere Episoden ...
        exporter.finalize()

    Args:
        out_dir: Zielverzeichnis des Datensatzes (wird bei Bedarf angelegt).
        fps:     Aufzeichnungsrate der Episoden [Hz], landet in ``meta/info.json``.
        arm:     Armseite, deren Gelenkzustand exportiert wird ("right").
    """

    def __init__(self, out_dir: str | Path, fps: int = 30, arm: str = "right") -> None:
        self._out_dir = Path(out_dir)
        self._fps = fps
        self._arm = arm
        self._episode_index = 0
        self._current_task: str | None = None
        self._current_steps: list[dict[str, Any]] = []
        self._episodes_meta: list[dict[str, Any]] = []
        self._tasks: dict[str, int] = {}

    def start_episode(self, task: str) -> None:
        """Beginnt eine neue Episode für die gegebene Aufgabe.

        Args:
            task: Sprechender Aufgabenname (z.B. "load_workpiece"), landet
                als Language-Annotation und in ``meta/tasks.jsonl``.
        """
        self._current_task = task
        self._current_steps = []
        if task not in self._tasks:
            self._tasks[task] = len(self._tasks)
        _log.info(
            "LerobotDatasetExporter: Episode %d gestartet (task=%s)",
            self._episode_index,
            task,
        )

    def add_step(self, obs: Observation, action: Action) -> None:
        """Hängt einen Schritt (Beobachtung + Aktion) an die laufende Episode an.

        Args:
            obs:    Beobachtung; ``obs.joint_state[arm]`` liefert den State,
                    fällt auf ``action.joint_targets`` zurück, falls fehlend.
            action: Aktion; ``joint_targets`` und ``gripper_closed`` gehen in
                    die Action-Modalitäten ein.

        Raises:
            RuntimeError: wenn keine Episode gestartet wurde (``start_episode``
                fehlt).
        """
        if self._current_task is None:
            raise RuntimeError(
                "LerobotDatasetExporter: add_step ohne vorherigen start_episode aufgerufen"
            )
        right_arm = (obs.joint_state or {}).get(self._arm) or action.joint_targets
        gripper = 1.0 if action.gripper_closed else 0.0
        step = {
            "frame_index": len(self._current_steps),
            "task": self._current_task,
            "state.right_arm": list(right_arm),
            "state.gripper": [gripper],
            "action.right_arm": list(action.joint_targets),
            "action.gripper": [gripper],
        }
        self._current_steps.append(step)

    def end_episode(self) -> None:
        """Schreibt die laufende Episode nach ``data/chunk-000/episode_<N>.jsonl``.

        Schreibt zusätzlich eine ``.parquet``-Datei, falls ``pyarrow``
        importierbar ist; sonst bleibt es bei JSONL.

        Raises:
            RuntimeError: wenn keine Episode gestartet wurde.
        """
        if self._current_task is None:
            raise RuntimeError(
                "LerobotDatasetExporter: end_episode ohne vorherigen start_episode aufgerufen"
            )
        chunk_dir = self._out_dir / "data" / "chunk-000"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        episode_path = chunk_dir / f"episode_{self._episode_index}.jsonl"
        with episode_path.open("w", encoding="utf-8") as f:
            for step in self._current_steps:
                f.write(json.dumps(step) + "\n")
        if _HAS_PYARROW:
            self._write_parquet(chunk_dir / f"episode_{self._episode_index}.parquet")
        self._episodes_meta.append(
            {
                "episode_index": self._episode_index,
                "task": self._current_task,
                "length": len(self._current_steps),
            }
        )
        _log.info(
            "LerobotDatasetExporter: Episode %d beendet (%d Schritte) -> %s",
            self._episode_index,
            len(self._current_steps),
            episode_path,
        )
        self._episode_index += 1
        self._current_task = None
        self._current_steps = []

    def _write_parquet(self, path: Path) -> None:
        """Schreibt die eben beendete Episode zusätzlich als Parquet-Datei.

        Wird nur aufgerufen, wenn ``pyarrow`` importierbar ist.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(self._current_steps)
        pq.write_table(table, path)

    def finalize(self) -> None:
        """Schreibt die Meta-Dateien: modality.json, info.json, episodes.jsonl, tasks.jsonl."""
        meta_dir = self._out_dir / "meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "modality.json").write_text(
            json.dumps(self._modality_json(), indent=2), encoding="utf-8"
        )
        (meta_dir / "info.json").write_text(
            json.dumps(self._info_json(), indent=2), encoding="utf-8"
        )
        with (meta_dir / "episodes.jsonl").open("w", encoding="utf-8") as f:
            for episode in self._episodes_meta:
                f.write(json.dumps(episode) + "\n")
        with (meta_dir / "tasks.jsonl").open("w", encoding="utf-8") as f:
            for task, index in self._tasks.items():
                f.write(json.dumps({"task_index": index, "task": task}) + "\n")
        _log.info(
            "LerobotDatasetExporter: finalize -> %s (%d Episoden)",
            meta_dir,
            len(self._episodes_meta),
        )

    def _modality_json(self) -> dict[str, Any]:
        """H2-Modality-Struktur analog ``groot/meta_modality.example.json``."""
        return {
            "state": {
                "right_arm": {"start": 0, "end": 7},
                "gripper": {"start": 7, "end": 8},
            },
            "action": {
                "right_arm": {"start": 0, "end": 7},
                "gripper": {"start": 7, "end": 8},
            },
            "video": {
                "head": {"original_key": "observation.images.head"},
                "wrist": {"original_key": "observation.images.wrist"},
            },
            "annotation": {
                "human.task_description": {"original_key": "task_index"},
            },
        }

    def _info_json(self) -> dict[str, Any]:
        """Basis-Metadaten des Datensatzes für ``meta/info.json``."""
        return {
            "robot_type": "unitree_h2",
            "codebase_version": "v2.0",
            "fps": self._fps,
            "total_episodes": len(self._episodes_meta),
        }
