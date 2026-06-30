# Snapshot v0.7.0 — GR00T-Zielarchitektur dokumentiert (2026-06-30)

Eingefrorene Kopie der **in v0.7.0 neuen/geänderten Dateien** (Delta gegenüber v0.6.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Endziel „NVIDIA Isaac GR00T als Steuerungs-Policy" als Zielarchitektur festgehalten (Doku-only,
KEIN Code). Verifizierte Fakten aus github.com/NVIDIA/Isaac-GR00T (N1.7, ~3B, Apache-2.0; H2 =
NEW_EMBODIMENT; AGX Thor ~10,7 Hz TensorRT). Integrations-Seam (künftiges PolicyInterface / GrootPolicy)
nur beschrieben. Erfundene Zahlen/Termine vor Commit entfernt.

Enthalten (Delta):
- `docs/roadmap_groot.md`, `docs/adr/0007-groot-policy-backend-zielarchitektur.md` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.7.0: nur Doku; `pytest` 96/96 weiterhin grün; Halluzinations-Check sauber.
