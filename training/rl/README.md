# RL-Locomotion-Training (MJX + Brax PPO auf GPU)

GPU-beschleunigtes Reinforcement-Learning für Humanoid-Laufen mit **MuJoCo Playground**
(MJX) + **Brax PPO**. Läuft auf einer einzelnen GPU — verifiziert sogar auf einer alten
**Quadro M4000 (Maxwell, sm_52, 8 GB)**.

> Hintergrund: Ein handgebauter, positionsgeregelter Gehregler (siehe `training/gait/`) balanciert
> den H2 nicht stabil (instabiles Gleichgewicht, ~2–4 s). RL löst genau dieses Balanceproblem.

## Umgebung (auf dem Trainings-Linux-Rechner, einmalig)

Separate venv, damit die `h2_loader`-Umgebung unberührt bleibt:

```sh
uv venv ~/mjxenv --python 3.11
uv pip install --python ~/mjxenv/bin/python "jax[cuda12]"      # läuft auf sm_52!
uv pip install --python ~/mjxenv/bin/python "mujoco==3.10.0" mujoco-mjx brax playground
```

### Verifizierte Versions-Fallen (alle im Skript behandelt)

1. **PyTorch cu130 ≠ Maxwell** — CUDA 13 hat Maxwell fallengelassen; NUR JAX (CUDA-12-Wheels)
   läuft auf sm_52. (Betrifft nur die Torch-Deploy-Pfade, nicht dieses Training.)
2. **MJX ≠ Mesh/Zylinder-Kollision** — Trainingsmodelle brauchen vereinfachte Kollision
   (Primitive). Die Playground-G1/H1-Modelle sind bereits MJX-tauglich; ein H2-Trainingsmodell
   muss entsprechend aufbereitet werden (Mesh/Zylinder-Kollision aus, Fuß-Boxen + Ebene).
3. **Playground default `impl='warp'` crasht** hier (mujoco_warp-Typbug) → Skript setzt
   `cfg.impl='jax'`.
4. **brax-Domain-Randomizer braucht Playgrounds Wrapper** → `wrap_env_fn=wrapper.wrap_for_brax_training`.
5. **brax 0.14.2 nutzt `jax.device_put_replicated`** (in jax ≥0.10 entfernt) → Single-GPU-Shim
   im Skript (`_ensure_device_put_replicated`).
6. **8 GB VRAM** → `num_envs` klein halten (Default 8192 ⇒ OOM). 256–1024 getestet.

## Training starten (entkoppelt, schreibt auf Platte)

Wichtig: Über eine instabile SSH-Verbindung (z. B. Tailscale-DERP-Relay) lassen sich
Hintergrundprozesse nicht zuverlässig per `nohup`/`screen` starten. **Robust: `systemd-run`** —
läuft als transiente Unit unabhängig von der SSH-Session, schreibt Logs + Checkpoints auf die
Festplatte, überlebt Verbindungsabbrüche und Offline-Gehen:

```sh
sudo systemd-run --unit=g1full --uid=ema --gid=ema --setenv=HOME=/home/ema \
    --working-directory=/home/ema/H2plus \
    -p StandardOutput=truncate:/home/ema/g1_full.log \
    -p StandardError=append:/home/ema/g1_full.log \
    /home/ema/mjxenv/bin/python /home/ema/H2plus/training/rl/train_playground.py \
        --env G1JoystickFlatTerrain --num-timesteps 150000000 --num-envs 1024 \
        --out-dir /home/ema/h2_rl_runs/g1_full
```

Smoke-Test (Minuten): `... train_playground.py --env G1JoystickFlatTerrain --smoke`

## Fortschritt prüfen (jederzeit, auch nach Offline-Pause)

```sh
systemctl is-active g1full                              # laeuft noch?
tail -f ~/h2_rl_runs/g1_full/metrics.jsonl              # Reward je Eval (JSON-Zeilen)
ls ~/h2_rl_runs/g1_full/{best,ckpt_*,final}             # Checkpoints auf Platte
```

`metrics.jsonl` enthält pro Eval u. a. `eval/episode_reward` (+ Einzelterme) und `eval/sps`.
`best/` = bester Parameterstand, `ckpt_<step>/` = periodisch, `final/` = Endstand,
`env_meta.json` = Env-Metadaten fürs spätere Deployment.

## Ausgabe deployen

Die gespeicherten Parameter werden über `make_inference_fn` + `params` geladen und liefern eine
Policy `obs → action`, die in die H2-Deploy-Pipeline (`training/deploy/`, namensbasiertes
Gelenk-Mapping) eingehängt wird. Für H2 muss zuvor ein H2-Trainings-Env (MJX-taugliches Modell +
Env-Klasse aus der G1-Vorlage) erstellt und trainiert werden — G1 dient als Pipeline-Beleg/Baseline.
