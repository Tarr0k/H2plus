# Snapshot v0.15.0 — Twin-Deployment (ematalos) + VNC-Viewer (2026-07-06)

Eingefrorene Kopie der **in v0.15.0 neuen/geänderten Dateien** (Delta gegenüber v0.14.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: Deployment des Twin-Stacks auf dem realen Ubuntu-Rechner `ematalos` (per SSH/Tailscale) und
`scripts/setup_vnc_viewer.sh` (TigerVNC :2 + openbox + H2-MuJoCo-Viewer-Autostart). Der H2 ist über VNC
(Tailscale 100.68.27.117:5902) im MuJoCo-Viewer sichtbar. Kein Code am h2_loader-Paket geändert.

Enthalten (Delta):
- `scripts/setup_vnc_viewer.sh` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.15.0: H2-Viewer-Fenster auf VNC :2 bestätigt (ematalos); `bash -n` grün;
`pytest` (Windows-Dev) 195 passed, 1 skipped unverändert.

Offen: voller DDS-Twin (Unitree `simulate_python`-Bridge wirft bei H2 IndexError — separater Fix).
