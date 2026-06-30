# Snapshot v0.10.0 — Induktorwechsel-Ausbau (2026-06-30)

Eingefrorene Kopie der **in v0.10.0 neuen/geänderten Dateien** (Delta gegenüber v0.9.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Induktorwechsel (Führung, 2 Schrauben) — Werkzeugwechsel (Greifer ↔ Schrauber) via `ToolChanger`.
Damit sind alle drei Kernaufgaben sim-vollständig (Laden, Entladen, Induktorwechsel).

Enthalten (Delta):
- `src/h2_loader/hal/end_effector/screwdriver.py`, `src/h2_loader/hal/tool_changer.py` (neu)
- `config/poses/inductor_screw_1.yaml`, `inductor_screw_2.yaml`, `inductor_pick.yaml`, `inductor_place.yaml` (neu)
- `tests/test_change_inductor.py` (neu)
- `src/h2_loader/hal/arm.py` (set_end_effector), `skills/base.py` (_reach in Basis + tool_changer),
  `skills/load_workpiece.py`, `skills/unload_workpiece.py`, `skills/change_inductor.py` (implementiert),
  `plc/plc_simulator.py` (CHANGE_INDUCTOR), `app.py` (--job, ToolChanger) (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.10.0: `pytest` 157/157 grün; `--job change_inductor` → voller Zyklus
(Tool-Change 2×, loosen 2×, tighten 2×), result=OK; LOAD weiterhin OK.
