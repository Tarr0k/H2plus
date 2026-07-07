# Snapshot v0.22.0 — DdsTwinDriver: h2_loader-App fährt den DDS-Twin (2026-07-07)

Delta gegenüber v0.21.0. Append-only Versionssicherung; Baseline siehe `docs/versions/v0.1/`.

## Inhalt
Der DDS-Steuerpfad (v. a. nach dem Bridge-Fix + `dds_hold_h2.py`-Nachweis) wird produktiv: ein regulärer
Treiber im `h2_loader`-Paket, sodass die GESAMTE Anwendung (Orchestrator + Lade-Skills) gegen den
unitree_mujoco-Physik-Twin laufen kann — ohne echte Hardware.

## Neu (Delta)
- `src/h2_loader/hal/drivers/dds_twin_driver.py` — `DdsTwinDriver(RobotDriverInterface)`: Ganzkörper-LowCmd
  (unitree_hg, 31 Motoren, Domain 1/lo), Hintergrund-Sende-Thread @200 Hz, Beine/Taille/Kopf auf Stehpose
  gehalten, Arme via `send_joints`, `read_state` aus `rt/lowstate`. Lazy SDK-Import.
- `src/h2_loader/app.py` — `--driver twin` (neben `sim`/`sdk`).
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

## Verifiziert
- pytest 195 passed / 1 skipped (unverändert).
- Gegen laufenden Twin: `send_joints("left", …)` → Arm trackt Sollwerte (shoulder_pitch→0.5, elbow→0.88),
  `read_state` liest zurück. CPU-only.

## Grenzen / Nächstes
Reiner Positions-Halteregler stabilisiert die Beine nicht dauerhaft (ADR-0008, kippt ~2 s) — Balance
liefert die RL-Policy (Training läuft). Nächste Schritte: Lade-Skill-Armposen (Teach-in) gegen den Twin;
RL-Beinbefehle als LowCmd-Quelle einhängen (Obs-aus-LowState-Bridge).
