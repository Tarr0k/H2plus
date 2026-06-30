# Snapshot v0.5.1 — Korrekturen aus der offiziellen H2-Doku (2026-06-29)

Eingefrorene Kopie der **in v0.5.1 neuen/geänderten Dateien** (Delta gegenüber v0.5.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Korrekturen aus der offiziellen Unitree-H2-Doku (via Browser-Extension extrahiert).
Kernpunkte: kein Modell „H2 Plus" (Varianten H2 / H2 EDU); **Secondary Development braucht H2 EDU**;
Onboard-Compute korrigiert (i5/i7/Jetson Thor statt „Blackwell/128 GB"); Debug-Modus Pflicht für
SDK-Steuerung; PR/AB-Steuermodi; DDS-Topics/IDL.

Enthalten (Delta):
- `docs/unitree_docs/Unitree_H2_Zusammenfassung.md` (neu, offizielle Doku-Extraktion)
- `docs/sdk_reference.md` (Korrektur-Abschnitt), `src/h2_loader/hal/drivers/unitree_sdk_driver.py` (Docstring)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.5.1: nur Doku/Docstrings; `pytest` 78/78 weiterhin grün.
