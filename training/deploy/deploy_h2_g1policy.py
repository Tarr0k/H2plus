"""deploy_h2_g1policy.py -- Experiment: G1-Lauf-Policy auf dem H2 im MuJoCo-Twin.

Fuehrt die vortrainierte Unitree-G1-Policy (unitree_rl_gym/deploy/pre_train/g1/motion.pt)
auf dem VOLLEN H2-Modell (31 Aktuatoren) aus. Nur die 12 Beingelenke werden von der
Policy geregelt; Taille/Arme/Kopf werden auf ihrer Neutralpose gehalten.

Warum das ueberhaupt geht: G1 und H2 teilen die Beinstruktur exakt (12 Bein-DoF,
Beobachtung obs=47, Aktion action=12). Die Policy ist damit dimensional lauffaehig
auf H2. Es findet KEIN Training statt -- reine CPU-Inferenz.

WICHTIG (verifizierte Falle): H2-Knoechelreihenfolge ist (ankle_roll, ankle_pitch),
G1 erwartet (ankle_pitch, ankle_roll). Zusaetzlich unterscheidet sich beim vollen
H2-Modell die Aktuator-Reihenfolge (Beine, Taille, Arme, Kopf) von der Gelenk-
Reihenfolge in qpos (Beine, Taille, Kopf, Arme). Beides wird hier geloest, indem die
12 Beingelenke strikt NAMENSBASIERT in der G1-Reihenfolge abgegriffen werden
(mj_name2id + actuator_trnid + jnt_qposadr/jnt_dofadr).

Erwartung: Da H2 rund doppelt so schwer/gross ist wie G1, ist stabiles Laufen NICHT
zu erwarten -- dies ist ein GPU-freier Machbarkeits-/Lebenszeichen-Test, kein fertiger
Laufregler. Mit --kp-scale lassen sich die Bein-Gains fuer die groessere H2-Masse
anheben (experimentell).

Aufruf in der VNC-Session (mit GPU-Rendering ueber VirtualGL):
    DISPLAY=:2 vglrun -d egl ~/H2plus/.venv/bin/python deploy_h2_g1policy.py \
        --xml    ~/unitree_mujoco/unitree_robots/h2/scene.xml \
        --policy ~/unitree_rl_gym/deploy/pre_train/g1/motion.pt \
        --vx 0.5
"""
from __future__ import annotations

import argparse
import time

import mujoco
import mujoco.viewer
import numpy as np
import torch

# ---- G1-Referenzwerte (aus unitree_rl_gym deploy/deploy_mujoco/configs/g1.yaml) ----
# Beinreihenfolge der G1-Policy (pro Seite: hip_pitch, hip_roll, hip_yaw, knee,
# ankle_pitch, ankle_roll). Exakt diese Namen greifen wir im H2-Modell ab -- dadurch
# ist der H2-Knoechel-Swap automatisch korrekt.
POLICY_LEG_JOINTS = [
    "left_hip_pitch", "left_hip_roll", "left_hip_yaw", "left_knee",
    "left_ankle_pitch", "left_ankle_roll",
    "right_hip_pitch", "right_hip_roll", "right_hip_yaw", "right_knee",
    "right_ankle_pitch", "right_ankle_roll",
]
KPS = np.array([100, 100, 100, 150, 40, 40, 100, 100, 100, 150, 40, 40], dtype=np.float32)
KDS = np.array([2, 2, 2, 4, 2, 2, 2, 2, 2, 4, 2, 2], dtype=np.float32)
DEFAULT_ANGLES = np.array(
    [-0.1, 0.0, 0.0, 0.3, -0.2, 0.0, -0.1, 0.0, 0.0, 0.3, -0.2, 0.0], dtype=np.float32
)
ANG_VEL_SCALE = 0.25
DOF_POS_SCALE = 1.0
DOF_VEL_SCALE = 0.05
ACTION_SCALE = 0.25
CMD_SCALE = np.array([2.0, 2.0, 0.25], dtype=np.float32)
NUM_ACTIONS = 12
NUM_OBS = 47
PERIOD = 0.8          # Gait-Zyklus [s]
SIM_DT = 0.002        # 500 Hz Physik
CONTROL_DECIMATION = 10  # -> 50 Hz Policy
# Halte-Gains fuer die nicht von der Policy geregelten Gelenke (Taille/Arme/Kopf).
HOLD_KP = 80.0
HOLD_KD = 2.0


def gravity_orientation(quat: np.ndarray) -> np.ndarray:
    """Schwerkraftrichtung im Basis-Frame (identisch zu deploy_mujoco.py)."""
    qw, qx, qy, qz = quat
    g = np.zeros(3, dtype=np.float32)
    g[0] = 2 * (-qz * qx + qw * qy)
    g[1] = -2 * (qz * qy + qw * qx)
    g[2] = 1 - 2 * (qw * qw + qz * qz)
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description="G1-Policy auf H2 im MuJoCo-Twin")
    ap.add_argument("--xml", required=True, help="Pfad zu H2 scene.xml")
    ap.add_argument("--policy", required=True, help="Pfad zu G1 motion.pt")
    ap.add_argument("--vx", type=float, default=0.5, help="Sollgeschwindigkeit vorwaerts [m/s]")
    ap.add_argument("--vy", type=float, default=0.0, help="Sollgeschwindigkeit seitlich [m/s]")
    ap.add_argument("--dyaw", type=float, default=0.0, help="Solldrehrate [rad/s]")
    ap.add_argument("--duration", type=float, default=120.0, help="Laufzeit [s]")
    ap.add_argument("--kp-scale", type=float, default=1.0,
                    help="Bein-Gains skalieren (H2 schwerer als G1 -> >1 testen)")
    ap.add_argument("--headless", action="store_true",
                    help="ohne Viewer laufen, nur Diagnose ausgeben (SSH-tauglich)")
    args = ap.parse_args()

    m = mujoco.MjModel.from_xml_path(args.xml)
    d = mujoco.MjData(m)
    m.opt.timestep = SIM_DT

    # --- Namensbasiertes Mapping: Policy-Beinreihenfolge -> H2 ctrl/qpos/qvel ---
    def act_id(name: str) -> int:
        i = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
        if i < 0:
            raise SystemExit(f"Aktuator '{name}' nicht im Modell gefunden")
        return i

    leg_act = np.array([act_id(n) for n in POLICY_LEG_JOINTS], dtype=int)  # ctrl-Index je Policy-Bein
    leg_jnt = m.actuator_trnid[leg_act, 0]                                 # zugehoerige Gelenk-ID
    leg_qadr = m.jnt_qposadr[leg_jnt]                                      # qpos-Adressen
    leg_vadr = m.jnt_dofadr[leg_jnt]                                       # qvel-Adressen

    leg_set = set(leg_act.tolist())
    hold_act = np.array([i for i in range(m.nu) if i not in leg_set], dtype=int)
    hold_jnt = m.actuator_trnid[hold_act, 0]
    hold_qadr = m.jnt_qposadr[hold_jnt]
    hold_vadr = m.jnt_dofadr[hold_jnt]

    kps = KPS * args.kp_scale

    # Startpose: Keyframe falls vorhanden, sonst Beine auf Default stellen.
    if m.nkey > 0:
        mujoco.mj_resetDataKeyframe(m, d, 0)
    d.qpos[leg_qadr] = DEFAULT_ANGLES
    mujoco.mj_forward(m, d)
    hold_target = d.qpos[hold_qadr].copy()  # Oberkoerper auf Startpose halten

    policy = torch.jit.load(args.policy)
    cmd = np.array([args.vx, args.vy, args.dyaw], dtype=np.float32)

    action = np.zeros(NUM_ACTIONS, dtype=np.float32)
    target = DEFAULT_ANGLES.copy()
    obs = np.zeros(NUM_OBS, dtype=np.float32)
    counter = 0

    z0 = float(d.qpos[2])  # Basis-Starthoehe (fuer Sturz-Erkennung)
    print(f"[deploy] H2-Beine an ctrl-Index {leg_act.tolist()}; "
          f"{len(hold_act)} Halte-Aktuatoren; kp_scale={args.kp_scale}; cmd={cmd.tolist()}; "
          f"Starthoehe z0={z0:.3f} m")

    # nichtlokale Zustaende fuer den Schritt-Closure
    state = {"action": action, "target": target, "counter": counter}

    def one_step() -> None:
        """Ein Physik-Schritt inkl. Policy-Update alle CONTROL_DECIMATION Schritte."""
        tau_leg = (state["target"] - d.qpos[leg_qadr]) * kps - d.qvel[leg_vadr] * KDS
        d.ctrl[leg_act] = tau_leg
        tau_hold = (hold_target - d.qpos[hold_qadr]) * HOLD_KP - d.qvel[hold_vadr] * HOLD_KD
        d.ctrl[hold_act] = tau_hold

        mujoco.mj_step(m, d)
        state["counter"] += 1

        if state["counter"] % CONTROL_DECIMATION == 0:
            qj_s = (d.qpos[leg_qadr] - DEFAULT_ANGLES) * DOF_POS_SCALE
            dqj_s = d.qvel[leg_vadr] * DOF_VEL_SCALE
            grav = gravity_orientation(d.qpos[3:7])
            omega = d.qvel[3:6] * ANG_VEL_SCALE
            phase = (state["counter"] * SIM_DT % PERIOD) / PERIOD
            obs[:3] = omega
            obs[3:6] = grav
            obs[6:9] = cmd * CMD_SCALE
            obs[9:9 + NUM_ACTIONS] = qj_s
            obs[9 + NUM_ACTIONS:9 + 2 * NUM_ACTIONS] = dqj_s
            obs[9 + 2 * NUM_ACTIONS:9 + 3 * NUM_ACTIONS] = state["action"]
            obs[9 + 3 * NUM_ACTIONS:9 + 3 * NUM_ACTIONS + 2] = [
                np.sin(2 * np.pi * phase), np.cos(2 * np.pi * phase)
            ]
            state["action"] = policy(torch.from_numpy(obs).unsqueeze(0)).detach().numpy().squeeze()
            state["target"] = state["action"] * ACTION_SCALE + DEFAULT_ANGLES

    if args.headless:
        # Kein Fenster: feste Schrittzahl, sekuendliche Diagnose, Sturz-Erkennung.
        n_steps = int(args.duration / SIM_DT)
        fell_at = None
        for _ in range(n_steps):
            one_step()
            z = float(d.qpos[2])
            if state["counter"] % 500 == 0:  # ~1 s
                x = float(d.qpos[0])
                print(f"  t={state['counter']*SIM_DT:5.1f}s  z={z:.3f}m  x={x:+.3f}m  "
                      f"grav_z={gravity_orientation(d.qpos[3:7])[2]:+.2f}")
            # aufrecht: grav_z ~ -1; gekippt/gestuerzt: grav_z steigt Richtung 0.
            if fell_at is None and (z < z0 * 0.6 or gravity_orientation(d.qpos[3:7])[2] > -0.5):
                fell_at = state["counter"] * SIM_DT
                print(f"  >>> GESTUERZT bei t={fell_at:.2f}s (z={z:.3f}m) <<<")
                break
        dist = float(d.qpos[0])
        if fell_at is None:
            print(f"[deploy] STEHT/LAEUFT bis Ende ({args.duration:.0f}s), "
                  f"zurueckgelegt x={dist:+.2f}m")
        else:
            print(f"[deploy] Ergebnis: Sturz nach {fell_at:.2f}s, x={dist:+.2f}m")
        return

    def reset_pose() -> None:
        """H2 zurueck in die Startpose (fuer wiederholte Lauf-Versuche im Viewer)."""
        if m.nkey > 0:
            mujoco.mj_resetDataKeyframe(m, d, 0)
        else:
            mujoco.mj_resetData(m, d)
        d.qpos[leg_qadr] = DEFAULT_ANGLES
        mujoco.mj_forward(m, d)
        state["action"][:] = 0.0
        state["target"] = DEFAULT_ANGLES.copy()

    with mujoco.viewer.launch_passive(m, d) as viewer:
        start = time.time()
        while viewer.is_running() and time.time() - start < args.duration:
            step_start = time.time()
            one_step()
            # Auto-Reset bei Sturz -> Demo zeigt wiederholte Versuche.
            if d.qpos[2] < z0 * 0.6 or gravity_orientation(d.qpos[3:7])[2] > -0.5:
                reset_pose()
            viewer.sync()
            dt_left = m.opt.timestep - (time.time() - step_start)
            if dt_left > 0:
                time.sleep(dt_left)


if __name__ == "__main__":
    main()
