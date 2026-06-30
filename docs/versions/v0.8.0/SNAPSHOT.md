# Snapshot v0.8.0 — Policy-Seam (ADR-0007) (2026-06-30)

Eingefrorene Kopie der **in v0.8.0 neuen/geänderten Dateien** (Delta gegenüber v0.7.1).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: austauschbarer Manipulations-Policy-Seam aus ADR-0007. Neues `policy/`-Paket mit
`PolicyInterface`/`Observation`/`Action`, `ScriptedPolicy` (Teach-in), `GrootPolicy` (Stub, keine Inferenz),
`SafeguardedPolicy` (Gelenk-Clamping), `FallbackPolicy` (groot→scripted). Skills nutzen die Policy wenn
gesetzt; `app.py --policy scripted|groot`.

Enthalten (Delta):
- `src/h2_loader/policy/` (__init__, base, scripted_policy, groot_policy, safeguard, fallback) (neu)
- `tests/test_policy.py` (neu)
- `src/h2_loader/skills/base.py`, `skills/load_workpiece.py`, `skills/unload_workpiece.py`, `app.py` (geändert)
- `docs/adr/0007-groot-policy-backend-zielarchitektur.md` (Umsetzungsstand v0.8.0)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.8.0: `pytest` 111/111 grün; `--driver sim` (scripted) und `--policy groot`
(Fallback→scripted) jeweils result=OK.
