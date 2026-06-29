# Snapshot v0.3.0 — Locomotion-Layer (H2 ist mobil) (2026-06-29)

Eingefrorene Kopie der **in v0.3.0 neuen/geänderten Dateien** (Delta gegenüber v0.2.0).
Append-only Versionssicherung — nicht weiterentwickeln; neuer Snapshot je Meilenstein.
Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Korrektur der Grundannahme „Roboter steht" → der H2 PLUS ist mobil. Neue Locomotion-/
Navigations-Ebene (Interface + Onboard-Stub via SDK), benannte Stationen, mehrstufige Skills
(laufen + manipulieren). rl_gym als Standard verworfen (H2 nicht unterstützt) → Onboard-Regler.

Enthalten (Delta):
- `src/h2_loader/hal/locomotion/` (base.py, onboard_locomotion.py, __init__.py) (neu)
- `config/stations.yaml`, `tests/test_locomotion.py` (neu)
- `docs/adr/0004-h2-mobil-locomotion-layer.md` (neu)
- `src/h2_loader/util/config.py`, `skills/base.py`, `skills/load_workpiece.py`,
  `skills/unload_workpiece.py`, `skills/change_inductor.py`, `app.py` (geändert)
- `tests/conftest.py`, `tests/test_skills.py`, `tests/test_job_runner.py` (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.3.0: `pytest` 58/58 grün; `python -m h2_loader.app --driver sim` fährt den
vollen Job-Zyklus inkl. Lauf-Schritten (part_storage → machine) durch (result=OK).

Offene Folgeschritte: Sicherheit des fahrenden Roboters (Bereichsüberwachung/Personenschutz);
Schritt-Ebene auf UDT vereinheitlichen (aus v0.2.0).
