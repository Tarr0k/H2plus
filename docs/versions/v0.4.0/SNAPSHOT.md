# Snapshot v0.4.0 — Funktionaler Sicherheits-Supervisor (2026-06-29)

Eingefrorene Kopie der **in v0.4.0 neuen/geänderten Dateien** (Delta gegenüber v0.3.0).
Append-only Versionssicherung — nicht weiterentwickeln; neuer Snapshot je Meilenstein.
Baseline-Vollkopie siehe `docs/versions/v0.1/`.

⚠️ Inhalt: funktionaler (NICHT sicherheitsgerichteter) Sicherheits-Supervisor für den fahrenden H2.
Betriebsart getrennt/abgesichert. Echter Personenschutz bleibt hardwired/zertifiziert (extern).

Enthalten (Delta):
- `config/safety_zones.yaml` (neu)
- `src/h2_loader/core/safety.py` (SafetySupervisor), `src/h2_loader/util/config.py` (geändert)
- `src/h2_loader/hal/locomotion/safety_monitored.py` (neu)
- `src/h2_loader/plc/plc_simulator.py`, `src/h2_loader/app.py` (geändert)
- `docs/safety_concept.md`, `docs/adr/0005-sicherheitskonzept.md` (neu)
- `tests/test_safety.py` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.4.0: `pytest` 78/78 grün; Sperr-Nachweis (kein robotEnable / Zone belegt /
Not-Halt / unbekannte Station → blockiert, speed 0.0); Sim-Dry-Run läuft bei Freigabe (result=OK).

Offene Folgeschritte: zertifizierte Sicherheitstechnik + Risikobeurteilung ISO 12100 (extern, vor
Inbetriebnahme zwingend); Schritt-Ebene auf UDT vereinheitlichen.
