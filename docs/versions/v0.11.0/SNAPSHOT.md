# Snapshot v0.11.0 — Echter asyncua-OPC-UA-Client (2026-06-30)

Eingefrorene Kopie der **in v0.11.0 neuen/geänderten Dateien** (Delta gegenüber v0.10.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: OPC-UA-Transport via asyncua (cross-platform, läuft auf Windows). Der `H2HandshakeClient` kann
optional über echtes OPC-UA statt In-Memory laufen — High-Level-Handshake unverändert. End-to-end gegen
einen lokalen asyncua-Server getestet (KEIN echtes SPS/Ubuntu nötig).

Enthalten (Delta):
- `src/h2_loader/plc/transport.py`, `src/h2_loader/plc/asyncua_transport.py` (neu)
- `tests/test_asyncua_transport.py` (neu, importorskip)
- `src/h2_loader/plc/handshake.py` (optional transport-backed), `pyproject.toml` ([plc] += asyncua>=2.0) (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.11.0: ohne asyncua `pytest` 157 passed + 1 skipped; mit asyncua 2.0.1
(Python 3.14) 162/162 grün (5 OPC-UA-Loopback-Tests). Hinweis: unter Python 3.14 ist asyncua 2.0.1 nötig.
