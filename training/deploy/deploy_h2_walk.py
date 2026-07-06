"""deploy_h2_walk.py -- modellbasierter (nicht lernender) Gehregler fuer den H2.

Im Unterschied zu `deploy_h2_g1policy.py` (G1-Lauf-Policy, neuronales Netz,
Torch-Inferenz) kommt hier **kein** maschinelles Lernen zum Einsatz: Ein
quasi-statischer Gangplaner (`training/gait/gait.py`, `QuasiStaticGait`)
liefert pro Zeitschritt Soll-Fusspositionen und eine geplante Beckenpose; eine
analytische inverse Kinematik pro Bein (`training/gait/leg_ik.py`, DLS gegen
MuJoCos eigene Jacobi-Matrix) loest daraus die 12 Beingelenkwinkel, die per
PD-Regelung angefahren werden. Abhaengigkeiten: nur `numpy` und `mujoco`
(>=3.1), reine CPU-Rechnung.

Wiederverwendetes Muster aus `deploy_h2_g1policy.py`: namensbasiertes
Aktuator-/Gelenk-Mapping (mj_name2id + actuator_trnid + jnt_qposadr/
jnt_dofadr), PD-Regelung ueber `d.ctrl`, `gravity_orientation`-Helfer,
Headless-Diagnose mit Sturzerkennung sowie Viewer-Modus.

Aufruf (Beispiel, im MuJoCo-Twin auf dem Ziel-Linux-Rechner):
    python deploy_h2_walk.py --xml ~/unitree_mujoco/unitree_robots/h2/scene.xml \
        --vx 0.1 --headless
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

# Standalone-Skript ausserhalb des installierbaren Pakets (wie
# `deploy_h2_g1policy.py`, siehe training/README.md) -- Repo-Wurzel unabhaengig
# vom Ausfuehrungsort auf den Suchpfad legen, damit `training.gait.*` importierbar ist.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from training.gait.balance import AnkleStrategyBalance  # noqa: E402
from training.gait.gait import GaitParams, QuasiStaticGait  # noqa: E402
from training.gait.leg_ik import POLICY_LEG_JOINTS_LEFT, POLICY_LEG_JOINTS_RIGHT  # noqa: E402
from training.gait.walk_controller import WalkController  # noqa: E402

POLICY_LEG_JOINTS = POLICY_LEG_JOINTS_LEFT + POLICY_LEG_JOINTS_RIGHT

SIM_DT = 0.002           # 500 Hz Physik
CONTROL_DECIMATION = 10  # -> 50 Hz Regel-Update
SETTLE_TIME = 0.3        # [s] Einschwingzeit nach dem Aufsetzen der Startpose, vor Gangstart

# Halte-Gains fuer die nicht vom Gang geregelten Gelenke (Taille/Arme/Kopf).
HOLD_KP = 80.0
HOLD_KD = 2.0


def gravity_orientation(quat: np.ndarray) -> np.ndarray:
    """Schwerkraftrichtung im Basis-Frame (identisch zu deploy_h2_g1policy.py)."""
    qw, qx, qy, qz = quat
    g = np.zeros(3, dtype=np.float32)
    g[0] = 2 * (-qz * qx + qw * qy)
    g[1] = -2 * (qz * qy + qw * qx)
    g[2] = 1 - 2 * (qw * qw + qz * qz)
    return g


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Modellbasierter quasi-statischer Gehregler fuer den H2 (kein ML)"
    )
    ap.add_argument("--xml", required=True, help="Pfad zu H2 scene.xml")
    ap.add_argument("--vx", type=float, default=0.1, help="Sollgeschwindigkeit vorwaerts [m/s]")
    ap.add_argument("--duration", type=float, default=30.0, help="Laufzeit [s]")
    ap.add_argument("--kp", type=float, default=400.0, help="Bein-P-Gain (PD-Regelung)")
    ap.add_argument("--kd", type=float, default=40.0, help="Bein-D-Gain (PD-Regelung)")
    ap.add_argument("--balance-kp", type=float, default=0.7,
                     help="Ankle-Strategie: P-Anteil auf die Rumpfneigung (0 = aus)")
    ap.add_argument("--balance-kd", type=float, default=0.6,
                     help="Ankle-Strategie: Daempfung auf die Basis-Winkelgeschwindigkeit")
    ap.add_argument("--foot-x-offset", type=float, default=None,
                     help="Fuss-Vorversatz vor dem Becken [m] (CoM ueber Knoechel)")
    ap.add_argument("--pelvis-height", type=float, default=None,
                     help="nominale Beckenstandhoehe [m] (Default aus GaitParams)")
    ap.add_argument("--foot-lateral", type=float, default=None,
                     help="seitlicher Fussabstand zur Koerpermitte [m]")
    ap.add_argument("--step-length", type=float, default=None,
                     help="Referenz-Schrittlaenge pro Halbzyklus [m]")
    ap.add_argument("--step-height", type=float, default=None,
                     help="Schwungfuss-Anhebung [m]")
    ap.add_argument("--cycle-time", type=float, default=None,
                     help="Dauer eines vollen Doppelschritts [s]")
    ap.add_argument("--ds-ratio", type=float, default=None,
                     help="Anteil Doppelstand je Halbzyklus [0..1)")
    ap.add_argument("--headless", action="store_true",
                     help="ohne Viewer laufen, nur Diagnose ausgeben (SSH-tauglich)")
    args = ap.parse_args()

    # GaitParams mit den GaitParams-Defaults vorbelegen, nur explizit gesetzte
    # CLI-Flags ueberschreiben sie.
    default_params = GaitParams()
    params = GaitParams(
        pelvis_height=args.pelvis_height if args.pelvis_height is not None else default_params.pelvis_height,
        foot_lateral=args.foot_lateral if args.foot_lateral is not None else default_params.foot_lateral,
        step_length=args.step_length if args.step_length is not None else default_params.step_length,
        step_height=args.step_height if args.step_height is not None else default_params.step_height,
        cycle_time=args.cycle_time if args.cycle_time is not None else default_params.cycle_time,
        ds_ratio=args.ds_ratio if args.ds_ratio is not None else default_params.ds_ratio,
        foot_x_offset=args.foot_x_offset if args.foot_x_offset is not None else default_params.foot_x_offset,
    )

    # Balance-Regler (Ankle-Strategie); balance_kp=0 schaltet ihn ab.
    balance = AnkleStrategyBalance(kp=args.balance_kp, kd=args.balance_kd)

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

    kps = np.full(12, args.kp, dtype=np.float64)
    kds = np.full(12, args.kd, dtype=np.float64)

    # --- Gangplaner + Controller, Startpose per IK loesen ---
    gait = QuasiStaticGait(params)
    controller = WalkController(m, gait)
    q0 = controller.initial_pose()  # (12,) Policy-Reihenfolge, IK-Loesung fuer t=0

    # Becken auf die geplante Startpose setzen (Position ueber der Modellwurzel,
    # aufrecht) -- das H2-Modell hat keinen Keyframe (m.nkey == 0, verifiziert).
    d.qpos[0:3] = [0.0, 0.0, params.pelvis_height]
    d.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    d.qpos[leg_qadr] = q0
    mujoco.mj_forward(m, d)
    hold_target = d.qpos[hold_qadr].copy()  # Oberkoerper/Kopf auf Startpose halten

    z0 = float(d.qpos[2])  # Beckenstarthoehe (fuer Sturz-Erkennung)
    print(f"[deploy] H2-Beine an ctrl-Index {leg_act.tolist()}; "
          f"{len(hold_act)} Halte-Aktuatoren; vx={args.vx:.2f} m/s; "
          f"kp={args.kp:.0f} kd={args.kd:.1f}; z0={z0:.3f} m; params={params}")

    state = {"counter": 0, "target": q0.copy()}

    def apply_pd() -> None:
        """PD-Regelung: 12 Beingelenke auf `state['target']` (+ Balance-Korrektur),
        Rest auf Halteziel."""
        grav = gravity_orientation(d.qpos[3:7])
        corr = balance.correct(grav, d.qvel[3:6])  # additive Knoechelkorrektur (12,)
        tau_leg = (state["target"] + corr - d.qpos[leg_qadr]) * kps - d.qvel[leg_vadr] * kds
        d.ctrl[leg_act] = tau_leg
        tau_hold = (hold_target - d.qpos[hold_qadr]) * HOLD_KP - d.qvel[hold_vadr] * HOLD_KD
        d.ctrl[hold_act] = tau_hold

    # --- Einschwingphase: Startpose halten, bis Bodenkontakt/PD-Kraefte sich
    #     beruhigt haben, BEVOR die Gangzeit (t=0 fuer den Gangplaner) beginnt.
    settle_steps = int(SETTLE_TIME / SIM_DT)
    for _ in range(settle_steps):
        apply_pd()
        mujoco.mj_step(m, d)

    def one_step(t_gait: float) -> None:
        """Ein Physik-Schritt inkl. Gang-Update alle CONTROL_DECIMATION Schritte."""
        if state["counter"] % CONTROL_DECIMATION == 0:
            state["target"] = controller.compute_targets(t_gait, args.vx)
        apply_pd()
        mujoco.mj_step(m, d)
        state["counter"] += 1

    if args.headless:
        # Kein Fenster, kein Auto-Reset (Ziel ist Stehen-/Laufenbleiben):
        # feste Schrittzahl, sekuendliche Diagnose, Sturz-Erkennung mit Abbruch.
        n_steps = int(args.duration / SIM_DT)
        fell_at = None
        for _ in range(n_steps):
            t_gait = state["counter"] * SIM_DT
            one_step(t_gait)
            z = float(d.qpos[2])
            grav_z = gravity_orientation(d.qpos[3:7])[2]
            if state["counter"] % 500 == 0:  # ~1 s
                x = float(d.qpos[0])
                print(f"  t={t_gait:5.1f}s  z={z:.3f}m  x={x:+.3f}m  grav_z={grav_z:+.2f}")
            # aufrecht: grav_z ~ -1; gekippt/gestuerzt: grav_z steigt Richtung 0.
            if fell_at is None and (z < z0 * 0.6 or grav_z > -0.5):
                fell_at = t_gait
                print(f"  >>> GESTUERZT bei t={fell_at:.2f}s (z={z:.3f}m) <<<")
                break
        dist = float(d.qpos[0])
        if fell_at is None:
            print(f"[deploy] STEHT/LAEUFT bis Ende ({args.duration:.0f}s), "
                  f"zurueckgelegt x={dist:+.2f}m")
        else:
            print(f"[deploy] Ergebnis: Sturz nach {fell_at:.2f}s, x={dist:+.2f}m")
        return

    with mujoco.viewer.launch_passive(m, d) as viewer:
        start = time.time()
        while viewer.is_running() and time.time() - start < args.duration:
            step_start = time.time()
            t_gait = state["counter"] * SIM_DT
            one_step(t_gait)
            viewer.sync()
            dt_left = m.opt.timestep - (time.time() - step_start)
            if dt_left > 0:
                time.sleep(dt_left)


if __name__ == "__main__":
    main()
