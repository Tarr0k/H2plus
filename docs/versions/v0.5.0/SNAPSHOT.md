# Snapshot v0.5.0 — SDK-Grounding (2026-06-29)

Eingefrorene Kopie der **in v0.5.0 neuen/geänderten Dateien** (Delta gegenüber v0.4.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Erdung der Stubs/Doku an den echten Unitree-SDK-Beispielen. Zentrale Korrektur: Onboard-
`LocoClient` ist velocity-/FSM-basiert, KEIN Wegpunkt-Fahren → `move_to(station)` braucht zusätzlich
eine Lokalisierungs-/Pfadschicht.

Enthalten (Delta):
- `docs/sdk_reference.md` (neu)
- `src/h2_loader/hal/locomotion/onboard_locomotion.py`, `src/h2_loader/hal/drivers/unitree_sdk_driver.py`
  (Docstrings geerdet)
- `docs/adr/0004-h2-mobil-locomotion-layer.md` (Nachtrag)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.5.0: nur Doku/Docstrings; `pytest` 78/78 weiterhin grün.
