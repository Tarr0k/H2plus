# Snapshot v0.16.0 — H2-Locomotion-Gerüst auf G1-Basis (2026-07-06)

Eingefrorene Kopie der **in v0.16.0 neuen/geänderten Dateien** (Delta gegenüber v0.15.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: GPU-freies Trainings-Gerüst für „H2 laufen lernen", abgeleitet vom Unitree G1 (beste Vorlage —
H2 und g1_29dof haben identische Gelenknamen/-struktur). Keine fertige H2-Lauf-Policy existiert → Training
nötig (RTX-GPU); Gewichte G1→H2 nicht übertragbar (Skala/Masse). Verifizierte Falle: Knöchel-Reihenfolge
H2 vs. G1 vertauscht (in der Config berücksichtigt).

Enthalten (Delta):
- `training/h2_locomotion_deploy.yaml`, `training/h2_joint_map.md`, `training/README.md` (neu)
- `docs/locomotion_training.md` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.16.0: `pytest` 195 passed, 1 skipped (training/ ohne Einfluss auf die Suite);
Knöchel-Reihenfolge H2 vs G1 unabhängig via gh api bestätigt.
