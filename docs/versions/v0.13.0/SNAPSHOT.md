# Snapshot v0.13.0 — Hardware-Bring-up + Digital-Twin (2026-07-03)

Eingefrorene Kopie der **in v0.13.0 neuen/geänderten Dateien** (Delta gegenüber v0.12.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

Inhalt: gestufter, sicherheits-gegateter Bring-up (`BringupSequencer` Phasen 0–4) + reale SDK-Adapter
(UnitreeSdkDriver, LocoClientVelocitySink; hardware-untested, SDK-treu, lazy import) + Digital-Twin-Anbindung
(unitree_mujoco, domain 1/lo). GR00T-untouched. SDK-Code am ersten Reallauf zu verifizieren.

Enthalten (Delta):
- `src/h2_loader/hal/h2_joint_index.py`, `src/h2_loader/bringup.py` (neu)
- `config/robot.real.yaml`, `config/robot.sim_mujoco.yaml`, `docs/bringup.md` (neu)
- `tests/test_h2_joint_index.py`, `tests/test_bringup.py`, `tests/test_hardware_smoke.py` (neu)
- `src/h2_loader/hal/drivers/unitree_sdk_driver.py`, `src/h2_loader/hal/locomotion/velocity_sink.py` (real ausimpl.)
- `pyproject.toml` (h2-bringup Script), `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

Verifikation zum Stand v0.13.0: `pytest` 195 passed, 1 skipped (Hardware-Smoke, importorskip + H2_HARDWARE=1);
Import von bringup/unitree_sdk_driver/h2_joint_index OHNE installiertes SDK erfolgreich (lazy imports).
