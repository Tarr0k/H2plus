# Snapshot v0.19.0 — GPU-RL-Training läuft auf der M4000 (MJX + Brax PPO) (2026-07-06)

Delta gegenüber v0.18.0. Append-only Versionssicherung; Baseline-Vollkopie siehe `docs/versions/v0.1/`.

## Inhalt

Durchbruch: **GPU-beschleunigtes RL-Locomotion-Training ist auf der vorhandenen alten Quadro M4000
(Maxwell, sm_52, 8 GB) machbar** — kein Kauf einer RTX nötig, „Tage Training" deckt die schwache GPU ab.
Training läuft **entkoppelt als systemd-Unit und schreibt Logs + Checkpoints auf die Festplatte**
(Offline-tauglich).

## Was funktioniert (verifiziert auf ematalos)

- **JAX + CUDA-12-Wheels laufen auf sm_52** (PyTorch cu130 nicht → nur JAX-Weg).
- **MJX + MuJoCo Playground `G1JoystickFlatTerrain`** (29-DoF Humanoid, ideal weil H2≈G1) trainiert
  mit Brax PPO auf der GPU (99 % Auslastung, ~7,45 GB stabil, kein OOM bei num_envs=1024).
- **Checkpointing auf Platte**: `metrics.jsonl` (Reward je Eval), `best/`, `ckpt_<step>/`, `final/`,
  `env_meta.json`. Smoke-Test komplett durchgelaufen; Langlauf (150M Schritte) gestartet.

## Vier Versions-Fallen gefixt (Skript + README)

1. Playground `impl='warp'` crasht → `cfg.impl='jax'`.
2. brax-Randomizer braucht Playgrounds Wrapper → `wrap_env_fn=wrapper.wrap_for_brax_training`.
3. brax 0.14.2 `jax.device_put_replicated` (in jax 0.10 entfernt) → Single-GPU-Shim.
4. 8 GB VRAM → `num_envs` klein halten.

## Start-Methode

`sudo systemd-run` (transiente Unit, SSH-entkoppelt, `StandardOutput=truncate:...log`) — robust gegen
instabile Verbindungen (Tailscale-DERP), nohup/screen/setsid scheitern dort. Details: `training/rl/README.md`.

## Enthalten (Delta)

- `training/rl/__init__.py`, `training/rl/train_playground.py`, `training/rl/README.md` (neu)
- `pyproject.toml`, `src/h2_loader/__init__.py`, `PROJECT_MEMORY.md` (geändert)

## Verifikation zum Stand v0.19.0

- Smoke-Test (200k Schritte, 256 Envs) komplett: GPU 99 %, metrics.jsonl + Checkpoints auf Platte.
- Langlauf `g1full` (150M Schritte, 1024 Envs) läuft stabil, kein OOM.
- `pytest` unverändert (training/ außerhalb der Suite).

## Nächster Schritt (Ziel H2)

H2-Trainings-Env bauen (MJX-taugliches H2-Modell mit vereinfachter Kollision + Env-Klasse aus der
G1-Vorlage) → H2 trainieren → Policy in die Deploy-Pipeline einhängen. G1 = Pipeline-Beleg/Baseline.
