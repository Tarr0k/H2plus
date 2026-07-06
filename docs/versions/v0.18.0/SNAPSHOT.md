# Snapshot v0.18.0 — Modellbasierter Gehregler (kein ML) + ehrlicher Befund (2026-07-06)

Eingefrorene Kopie der **in v0.18.0 neuen/geänderten Dateien** (Delta gegenüber v0.17.0).
Append-only Versionssicherung. Baseline-Vollkopie siehe `docs/versions/v0.1/`.

## Inhalt

GPU-freier, rein kinematischer Gehregler für den H2 im MuJoCo-Twin: quasi-statischer Gangplaner +
inverse Kinematik pro Bein (DLS via MuJoCo-Jacobi) + Ankle-Strategie-Balance, alles hinter Interfaces.

## Was funktioniert

- **Inverse Kinematik (`leg_ik.py`) — erstklassig:** Residuum ~1e-6 m, Fuß flach (0°), 2–4 Iterationen,
  beide Beine, alle typischen Schrittziele (vor/zurück/hoch/seitlich). Drei verifizierte Fallen gefixt:
  1. `mj_comPos` nach `mj_kinematics` nötig — sonst liefert `mj_jac` eine **Nullmatrix** (IK bewegt sich nicht).
  2. `mju_subQuat` liefert den Orientierungsfehler im **lokalen** Fuß-Frame → in den **Weltframe** drehen
     (jacr ist welt), sonst divergiert die 6D-IK.
  3. **Kaltstart aus q=0 divergiert** (gestreckte Beine = Knie-Singularität) → Default-Startschätzung =
     leichte Kniebeuge `[-0.3,0,0,0.6,-0.3,0]` + dq-Clamping.
- **Gangplaner + Deploy-Pipeline:** Gang-Sollwerte → pelvisrelative Fußziele → IK → 12 Gelenkwinkel → PD;
  namensbasiertes Mapping (löst Knöchel-Swap automatisch), headless-Diagnose + VNC-Viewer.
- **Austauschbarer `BalanceController`-Seam** (ABC) — später ZMP/Capture-Point/WBC einhängbar.

## Ehrlicher Befund (im Twin verifiziert)

Ein **positionsgeregelter H2 (72 kg, 29 DoF) ist ein instabiles Gleichgewicht** — er kippt selbst bei
perfekter Standpose ohne Rückkopplung nach ~1,7 s. Höhere Gains / steifere Knöchel verschlimmern das
(dynamische Instabilität, kein Kraftmangel — Aktuatoren sind unbegrenzte Drehmoment-Motoren).
Die Ankle-Strategie hält den Drift nahe null und verlängert auf ~4 s (best-tuning), **erreicht aber
kein stabiles Stehen/Gehen** (Sturz tuning-abhängig nach ~2–4 s).

→ **Robustes model-based Gehen braucht einen Ganzkörper-Balanceregler** (LIPM/Capture-Point +
Schrittanpassung bzw. Whole-Body-QP; mehrtägiges CPU-Regelungsprojekt) **oder eine gelernte Policy**
(Cloud-GPU, wenige Stunden). Genau deshalb dominiert RL bei Humanoid-Locomotion.

## Enthalten (Delta)

- `training/gait/__init__.py`, `training/gait/leg_ik.py`, `training/gait/gait.py`,
  `training/gait/balance.py`, `training/gait/walk_controller.py` (neu)
- `training/deploy/deploy_h2_walk.py` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

## Aufruf

```sh
# Headless (SSH): Stehen bzw. langsames Gehen
python training/deploy/deploy_h2_walk.py --xml <h2>/scene.xml --vx 0.0  --headless
python training/deploy/deploy_h2_walk.py --xml <h2>/scene.xml --vx 0.08 --headless
# Balance abschaltbar zum Vergleich: --balance-kp 0 --balance-kd 0
# Visuell im VNC: DISPLAY=:2 vglrun -d egl python training/deploy/deploy_h2_walk.py --xml <h2>/scene.xml --vx 0.05
```

## Verifikation zum Stand v0.18.0

- IK-Round-Trip 1e-6 m (beide Beine, mehrere Schrittziele) auf ematalos (MuJoCo 3.10).
- Stand/Gang headless im Twin (best-tuning ~4 s, dann Sturz — Grenze dokumentiert).
- `pytest` unverändert (training/ außerhalb der Suite).
