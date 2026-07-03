# Snapshot v0.12.0 — GR00T-Vorbereitung (2026-07-03)

Eingefrorene Kopie der **in v0.12.0 neuen/geänderten Dateien** (Delta gegenüber v0.11.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: GR00T-seitige Vorbereitung ohne Hardware — H2-NEW_EMBODIMENT-Modality-Config, LeRobot-v2-
Datensatz-Exporter (Gerüst), GrootPolicy-Adapter (Mapping fertig, Inferenz offen), Setup-Doku. GR00T selbst
läuft nur auf Linux+CUDA; diese Artefakte sind plattformneutral und liegen für den Rig bereit.

Enthalten (Delta):
- `groot/h2_modality_config.py`, `groot/meta_modality.example.json`, `groot/README.md` (neu, außerhalb src/)
- `src/h2_loader/dataset/__init__.py`, `src/h2_loader/dataset/lerobot_export.py` (neu)
- `docs/groot_setup.md` (neu)
- `tests/test_groot_export.py`, `tests/test_groot_policy_adapter.py` (neu)
- `src/h2_loader/policy/groot_policy.py` (Adapter), `src/h2_loader/policy/__init__.py` (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.12.0: `pytest` 174/174 grün (162+12); `groot/` wird von der Testsuite nicht
importiert (kein gr00t installiert). GR00T-Laufzeit weiterhin nur auf Ubuntu+CUDA-Rig.
