# Snapshot v0.14.0 — Ubuntu-Twin-Setup-Skript (2026-07-03)

Eingefrorene Kopie der **in v0.14.0 neuen/geänderten Dateien** (Delta gegenüber v0.13.1).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: idempotentes Installationsskript für den unitree_mujoco-Digital-Twin auf Ubuntu
(`scripts/setup_ubuntu_twin.sh`) — apt/CycloneDDS/unitree_sdk2/unitree_sdk2_python/MuJoCo/
unitree_mujoco/h2plus-venv/pytest, `--yes` + `sudo -n`. In docs/bringup.md verlinkt. Am Ziel-Ubuntu
ungetestet (hier nur `bash -n`).

Enthalten (Delta):
- `scripts/setup_ubuntu_twin.sh` (neu)
- `docs/bringup.md` (Skript-Verweis im Digital-Twin-Abschnitt)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.14.0: `bash -n` (Syntax) grün; `pytest` 195 passed, 1 skipped unverändert.
