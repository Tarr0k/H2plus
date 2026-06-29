# Snapshot v0.2.0 — Job-Dispatch + PLC-Simulator (2026-06-29)

Eingefrorene Kopie der **in v0.2.0 neuen/geänderten Dateien** (Delta gegenüber v0.1.1).
Append-only Versionssicherung — nicht weiterentwickeln; Änderungen am lebenden Projekt,
neuer Snapshot je Meilenstein. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt dieses Inkrements: OPC-UA-Handshake in den Ablauf verdrahtet (`JobRunner`) + Maschinen-
Simulator (`PlcSimulator`), sodass ein voller Job-Zyklus (Maschine fordert LOAD → H2 nimmt an →
Skill läuft → finish_job OK) ohne Hardware durchläuft und getestet ist.

Enthalten (Delta):
- `src/h2_loader/core/job_runner.py`, `src/h2_loader/plc/plc_simulator.py` (neu)
- `tests/test_job_runner.py` (neu)
- `src/h2_loader/util/config.py`, `src/h2_loader/app.py` (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.2.0: `pytest` 50/50 grün; `python -m h2_loader.app --driver sim` fährt
einen vollen Job-Zyklus durch (JobOutcome result=OK, skill_ran=True).

Bewusste Schuld: Job-Ebene über UDT, Schritt-Ebene noch über flaches `Signal`-Enum — Vereinheitlichung
auf UDT als Folgeschritt vorgemerkt (siehe PROJECT_MEMORY v0.2.0).
