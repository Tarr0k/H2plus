# Snapshot v0.17.0 — Experiment: G1-Policy direkt auf H2 im Twin (2026-07-06)

Eingefrorene Kopie der **in v0.17.0 neuen/geänderten Dateien** (Delta gegenüber v0.16.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

## Inhalt

GPU-freies Machbarkeits-/Lebenszeichen-Experiment: Kann man die vortrainierte **Unitree-G1-Lauf-Policy
einfach auf den H2 anwenden („hochskalieren")?** Antwort: Sie läuft dimensional sofort (G1↔H2 identische
Beinstruktur, obs=47, action=12) und H2 macht echte Schritte — kippt aber nach ~1,5 s, weil er ~2× so
schwer ist wie G1 (trainierte Balance passt nicht). Gain-Anheben ist kein Fix. **Bestätigt: echtes
Retraining auf RTX-GPU nötig.** Nutzen: die Deploy-Pipeline (obs→Policy→PD→H2) steht und funktioniert.

## Enthalten (Delta)

- `training/deploy/deploy_h2_g1policy.py` (neu) — G1-Policy-Runner auf vollem H2-MJCF.
  - Nur 12 Beingelenke policy-geregelt, Rest auf Startpose gehalten.
  - Namensbasiertes Mapping löst Knöchel-Swap **und** Aktuator/qpos-Reihenfolge-Mismatch automatisch.
  - `--headless` (SSH-Diagnose + Sturzerkennung) und Viewer-Modus mit Auto-Reset bei Sturz.
  - Obs/Scales/Gait-Phase 1:1 aus `unitree_rl_gym/deploy/deploy_mujoco.py`.
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

## Messergebnis (headless, reproduzierbar)

| kp_scale | vorwärts (vx=0,5) | Stehen (vx=0) |
|---|---|---|
| 1,0 (G1-Original) | Sturz 0,47 s | — |
| 2,0 | 0,75 m, Sturz 1,05 s | Sturz 1,11 s |
| **3,0 (Optimum)** | **0,86 m, Sturz 1,47 s** | Sturz 1,50 s |
| 4,0 / 5,0 | schlechter | schlechter |

## Aufruf

```sh
# Headless (Diagnose, SSH-tauglich):
python training/deploy/deploy_h2_g1policy.py \
    --xml    <h2>/scene.xml \
    --policy <unitree_rl_gym>/deploy/pre_train/g1/motion.pt \
    --vx 0.5 --kp-scale 3.0 --duration 15 --headless

# Visuell im VNC (GPU-Rendering via VirtualGL):
DISPLAY=:2 vglrun -d egl python training/deploy/deploy_h2_g1policy.py \
    --xml <h2>/scene.xml --policy <g1>/motion.pt --vx 0.5 --kp-scale 3.0
```

## Verifikation zum Stand v0.17.0

- headless-Gain-Sweep wie oben (auf ematalos, MuJoCo 3.10, CPU-Torch 2.12.1).
- Demo-Prozess stabil im VNC :2, GPU-gerendert.
- `pytest` unverändert (training/ ohne Einfluss auf die Suite).
- Voraussetzung Betrieb: `torch` (CPU) + `mujoco` + `unitree_rl_gym`-Klon (für die G1-`motion.pt`).
