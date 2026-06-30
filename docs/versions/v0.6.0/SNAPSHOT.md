# Snapshot v0.6.0 — Schritt-Ebene auf UDT (MachineIo) (2026-06-30)

Eingefrorene Kopie der **in v0.6.0 neuen/geänderten Dateien** (Delta gegenüber v0.5.1).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: löst die v0.2.0-Schuld „zwei PLC-Stores". Die Schritt-Ebene der Skills läuft jetzt über die UDT
(`H2HandshakeClient`) via neuer Fassade `MachineIo`. Flaches `Signal`/`PlcInterface`/`OpcUaPlcClient`
bleibt als Legacy erhalten (von Skills ungenutzt).

Enthalten (Delta):
- `src/h2_loader/plc/machine_io.py`, `tests/test_machine_io.py`, `docs/adr/0006-schritt-ebene-auf-udt.md` (neu)
- `src/h2_loader/plc/plc_simulator.py` (kein plc-Param, send_job-UDT-Seeding, service_requests),
  `skills/base.py` (plc→machine), `skills/load_workpiece.py`, `skills/unload_workpiece.py`, `skills/__init__.py`,
  `plc/signals.py`, `plc/base.py`, `plc/opcua_client.py` (Legacy-Hinweis), `app.py` (geändert)
- `tests/conftest.py`, `tests/test_skills.py`, `tests/test_job_runner.py` (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.6.0: `pytest` 96/96 grün; skills/ ohne Legacy-Importe; Sim-Dry-Run mit
UDT-Clamp-Handshake → result=OK.
