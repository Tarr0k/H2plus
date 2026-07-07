# Snapshot v0.20.0 — H2-Trainings-Env gebaut, H2-Langlauf gestartet (2026-07-07)

Delta gegenüber v0.19.0. Append-only Versionssicherung; Baseline-Vollkopie siehe `docs/versions/v0.1/`.

## Inhalt

Das **eigentliche Ziel** ist erreicht: eine MJX/MuJoCo-Playground-**Trainingsumgebung für den H2**, aus
der G1-Vorlage adaptiert, läuft auf der M4000 — H2 trainiert (GPU-RL) das Laufen. G1 diente als
Pipeline-Beweis/Baseline (konvergierte auf reward 7,09 / Episodenlänge 636) und wurde danach gestoppt.

## Neu (`training/rl/h2/`)

- `build_h2_mjx_model.py` — baut aus der echten H2-MJCF ein MJX-taugliches „feetonly"-Modell + Szene
  (Mesh/Zylinder-Kollision aus, Fuß-Boxen `left_foot`/`right_foot` + Sites, IMU-Sites → `imu_in_pelvis`/
  `imu_in_torso`, kompletter G1-Sensor-Block, `<position>`-Aktuatoren, Home-Keyframe per Vorwärtskinematik).
- `h2_constants.py`, `base.py` (`H2Env`), `joystick.py` (`H2JoystickFlatTerrain`), `randomize.py`, `README.md`
- `train_playground.py` erweitert: `--env H2JoystickFlatTerrain` (direkte Instanziierung, kein Registry-Eintrag).

## Kernpunkte

- **Aktuator-Reihenfolge ≠ qpos-Reihenfolge bei H2** (Arme/Kopf vertauscht ggü. G1) → Env adressiert
  jedes Gelenk namensbasiert (actuator_trnid→jnt_qposadr/dofadr), nie per `qpos[7:]`-Slice. Wichtigster
  Unterschied zur 1:1-G1-Kopie.
- Build-Bug gefixt: `strip_scene_assets()` entfernt Boden/groundplane/skybox aus der geflachten Kopie
  (sonst „repeated name 'groundplane'").
- Gelenkgrenzen als 90%-Fenster der echten `jnt_range` (keine erfundenen Zahlen); Aktuator-kp/damping als
  Fallback aus G1-Klassen, reale forcerange bevorzugt.

## Verifiziert auf ematalos

- `build_h2_mjx_model.py` → `h2_mjx_feetonly.xml` + Szene, **nq=38 nv=37 nu=31 nkey=1**.
- MJX `put_model(impl=jax)` OK; `H2JoystickFlatTerrain` instanziiert (obs state=109/priv=228, action=31);
  reset+step rechnen Reward.
- PPO-Smoke lief (Compile ~10 min; erste Eval step0 reward −5,72 / epLen 38 = Untrainiert-Baseline;
  best/+ckpt_0 + metrics.jsonl auf Platte).
- **H2-Langlauf `h2full` gestartet**: 150M Schritte, num_envs 1024, Domain-Randomizer, entkoppelt via
  systemd-run, Ausgabe unter `~/h2_rl_runs/h2_full/`.

## Nächster Schritt

H2-Langlauf beobachten (reward↑/Episodenlänge↑ wie G1) → nach Konvergenz Policy über
`make_inference_fn`+`params` in die Deploy-Pipeline (`training/deploy/`) einhängen + im VNC rendern.

## Hinweis

`training/rl/_g1_reference/` = lokale Kopie der G1-Playground-Env als Adaptionsvorlage (Apache-2.0,
DeepMind Technologies) — gitignored, nicht Teil des Commits.
