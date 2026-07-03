"""Tests für den GR00T-flavored LeRobot-v2-Export (ADR-0007, Stufe 1/2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from h2_loader.dataset import LerobotDatasetExporter
from h2_loader.policy.base import Action, Observation


def _make_steps(n: int) -> list[tuple[Observation, Action]]:
    """Baut n Observation/Action-Paare mit steigenden Gelenkwinkeln."""
    steps = []
    for i in range(n):
        obs = Observation(goal="load_workpiece", joint_state={"right": [0.1 * i] * 7})
        action = Action(arm="right", joint_targets=[0.1 * i] * 7, gripper_closed=(i % 2 == 0))
        steps.append((obs, action))
    return steps


def test_export_writes_meta_and_episode_files(tmp_path: Path) -> None:
    """Exporter schreibt alle meta/-Dateien + Episodendatei nach start/add/end/finalize."""
    exporter = LerobotDatasetExporter(tmp_path, fps=30, arm="right")
    exporter.start_episode("load_workpiece")
    for obs, action in _make_steps(5):
        exporter.add_step(obs, action)
    exporter.end_episode()
    exporter.finalize()

    meta_dir = tmp_path / "meta"
    assert (meta_dir / "modality.json").is_file()
    assert (meta_dir / "info.json").is_file()
    assert (meta_dir / "episodes.jsonl").is_file()
    assert (meta_dir / "tasks.jsonl").is_file()
    assert (tmp_path / "data" / "chunk-000" / "episode_0.jsonl").is_file()


def test_export_modality_json_contains_h2_keys(tmp_path: Path) -> None:
    """meta/modality.json enthält right_arm/gripper (state) und head/wrist (video)."""
    exporter = LerobotDatasetExporter(tmp_path)
    exporter.start_episode("load_workpiece")
    exporter.add_step(*_make_steps(1)[0])
    exporter.end_episode()
    exporter.finalize()

    modality = json.loads((tmp_path / "meta" / "modality.json").read_text(encoding="utf-8"))
    assert "right_arm" in modality["state"]
    assert "gripper" in modality["state"]
    assert "head" in modality["video"]
    assert "wrist" in modality["video"]


def test_export_episode_file_has_n_steps(tmp_path: Path) -> None:
    """Die Episode-Datei enthält genau n JSONL-Zeilen für n add_step-Aufrufe."""
    exporter = LerobotDatasetExporter(tmp_path)
    exporter.start_episode("load_workpiece")
    for obs, action in _make_steps(4):
        exporter.add_step(obs, action)
    exporter.end_episode()

    episode_path = tmp_path / "data" / "chunk-000" / "episode_0.jsonl"
    lines = episode_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4


def test_export_info_json_robot_type(tmp_path: Path) -> None:
    """meta/info.json enthält robot_type=='unitree_h2'."""
    exporter = LerobotDatasetExporter(tmp_path)
    exporter.start_episode("load_workpiece")
    exporter.add_step(*_make_steps(1)[0])
    exporter.end_episode()
    exporter.finalize()

    info = json.loads((tmp_path / "meta" / "info.json").read_text(encoding="utf-8"))
    assert info["robot_type"] == "unitree_h2"


def test_add_step_without_start_episode_raises(tmp_path: Path) -> None:
    """add_step ohne vorherigen start_episode wirft RuntimeError."""
    exporter = LerobotDatasetExporter(tmp_path)
    obs, action = _make_steps(1)[0]
    with pytest.raises(RuntimeError):
        exporter.add_step(obs, action)


def test_end_episode_without_start_episode_raises(tmp_path: Path) -> None:
    """end_episode ohne vorherigen start_episode wirft RuntimeError."""
    exporter = LerobotDatasetExporter(tmp_path)
    with pytest.raises(RuntimeError):
        exporter.end_episode()
