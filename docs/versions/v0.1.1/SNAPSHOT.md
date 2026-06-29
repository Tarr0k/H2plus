# Snapshot v0.1.1 — OPC-UA-UDT-Schnittstelle (2026-06-29)

Eingefrorene Kopie der **in v0.1.1 neuen/geänderten Dateien** (Delta gegenüber v0.1).
Append-only Versionssicherung — nicht weiterentwickeln; Änderungen erfolgen am lebenden Projekt,
neuer Snapshot je Meilenstein. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt dieses Inkrements: OPC-UA-Schnittstelle zwischen Siemens S7-1500 und Unitree H2 PLUS
(TIA-UDT + Python-Spiegel + Handshake-Stub + Tests + Spezifikation).

Enthalten (Delta):
- `tia/udt/H2_Interface_UDTs.scl`, `tia/README.md`
- `docs/plc_interface.md`
- `src/h2_loader/plc/udt.py`, `src/h2_loader/plc/handshake.py`
- `tests/test_plc_interface.py`
- `config/plc.yaml`, `pyproject.toml`, `src/h2_loader/__init__.py`
- `PROJECT_MEMORY.md`

Verifikation zum Stand v0.1.1: `pytest` 45/45 grün; Konsistenz-Check SCL-Member == Python-Feldkatalog
(7+13+16+5 = 41) OK.
