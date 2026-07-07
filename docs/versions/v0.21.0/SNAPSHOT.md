# Snapshot v0.21.0 — RL-Policy-Deploy-Harness (2026-07-07)

Delta gegenüber v0.20.0. Append-only Versionssicherung; Baseline-Vollkopie siehe `docs/versions/v0.1/`.

## Inhalt

Das Gegenstück zum Training: `training/deploy/deploy_playground_policy.py` lädt eine mit
`train_playground.py` trainierte Brax/JAX-PPO-Policy und lässt sie im MuJoCo-Playground-Env laufen —
Reward/Episodenlänge/Strecke headless, optional als MP4. Parallel zum laufenden H2-Training gebaut und
**an der bereits konvergierten G1-Policy validiert**, damit das Werkzeug für den finalen H2-Schritt
fertig ist.

## Verifiziert (G1-Policy `g1_full/best`)

- Summen-Reward **9,43**, **300 Schritte (6 s) ohne Sturz**, Strecke 1,47 m, Höhe 0,77 m gehalten → die
  trainierte G1-Policy läuft, sauber über den Harness geladen und ausgeführt.
- Das parallele H2-Training (`h2full`) lief dabei **ungestört** weiter (Deploy nutzt On-Demand-Allocator).

## Gelöste Deploy-Fallen

- Params = **Liste [Normalizer, Policy-Netz, Value-Netz]**; Inferenz braucht nur `(Normalizer, Policy)`.
- orbax liefert den **Normalizer als dict** → zurück in `running_statistics.RunningStatisticsState`
  (sonst „'dict' object has no attribute 'count'").
- orbax-Checkpoint trägt **cuda:0-Sharding** → nur auf der GPU wiederherstellbar; Start mit
  `XLA_PYTHON_CLIENT_ALLOCATOR=platform` belegt nur nötigen VRAM → koexistiert mit laufendem Training.
  Robuster Start via `systemd-run` (entkoppelt).

## Enthalten (Delta)

- `training/deploy/deploy_playground_policy.py` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

## Nutzung nach H2-Konvergenz

```sh
XLA_PYTHON_CLIENT_ALLOCATOR=platform python training/deploy/deploy_playground_policy.py \
    --env H2JoystickFlatTerrain --ckpt ~/h2_rl_runs/h2_full/best --steps 500 --video ~/h2_walk.mp4
```

## Stand Training

H2-Langlauf `h2full` läuft weiter (noch step-0-Baseline reward −5,72; Evals ~7,5 M Schritte getaktet).
Stündlicher Cron-Check (Job a308c5d6) meldet den Lernverlauf.
