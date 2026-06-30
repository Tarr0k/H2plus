# Snapshot v0.9.0 — Lokalisierungs-/Pfadschicht für move_to (2026-06-30)

Eingefrorene Kopie der **in v0.9.0 neuen/geänderten Dateien** (Delta gegenüber v0.8.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: `move_to(station)` als velocity-basierter Closed-Loop (der echte LocoClient kann kein
Wegpunkt-Fahren). Lokalisierung + P-Regler im Body-Frame; in Sim kinematische Integration + perfekte
Lokalisierung, am Zielsystem LiDAR-Odometrie + LocoClient. Keine Hindernisvermeidung (Vereinfachung).

Enthalten (Delta):
- `src/h2_loader/hal/locomotion/localization.py`, `velocity_sink.py`, `navigating_locomotion.py` (neu)
- `tests/test_navigation.py` (neu)
- `src/h2_loader/util/config.py` (StationsConfig.nav), `config/stations.yaml` (nav-Block), `src/h2_loader/app.py` (geändert)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.9.0: `pytest` 136/136 grün; Dry-Run fährt Stationen per Closed-Loop an,
result=OK.
