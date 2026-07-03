# Snapshot v0.13.1 — unitree_mujoco-Twin Setup-Befehle (2026-07-03)

Eingefrorene Kopie der **in v0.13.1 geänderten Dateien** (Delta gegenüber v0.13.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Digital-Twin-Abschnitt in `docs/bringup.md` um konkrete `unitree_mujoco`-Setup-Befehle erweitert
(C++- und Python-Variante, `-r h2`; H2-Modell ist im Repo enthalten; CPU-Physik, keine RTX-GPU nötig).

Enthalten (Delta):
- `docs/bringup.md` (Digital-Twin-Setup erweitert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.13.1: nur Doku; `pytest` 195 passed, 1 skipped unverändert.
