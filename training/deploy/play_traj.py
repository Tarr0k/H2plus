"""play_traj.py -- spielt eine gespeicherte qpos-Trajektorie live im MuJoCo-Fenster ab.

Bewusst OHNE JAX/Torch: lädt nur ein selbstenthaltenes MuJoCo-Modell (.mjb) und
eine qpos-Trajektorie (.npy) und rendert sie in Endlosschleife über den passiven
C-MuJoCo-Viewer. So laesst sich der Viewer problemlos unter `vglrun` (VirtualGL,
GPU-Rendern in der VNC-Session) starten -- getrennt vom GPU-Rollout, weil vglrun
JAXs CUDA-Erkennung stoert (daher rechnet `deploy_playground_policy.py --save-traj`
den Rollout separat auf der GPU und legt traj.npy + model.mjb ab).

Aufruf (in der VNC-Session, z. B. via xstartup):
    vglrun -d egl python play_traj.py <ordner_mit_model.mjb_und_traj.npy> [fps]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Aufruf: play_traj.py <ordner> [fps]   (ordner enthaelt model.mjb + traj.npy)")
    d = Path(sys.argv[1]).expanduser()
    fps = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0

    model = mujoco.MjModel.from_binary_path(str(d / "model.mjb"))
    traj = np.load(str(d / "traj.npy"))
    data = mujoco.MjData(model)
    dt = 1.0 / fps
    print(f"[play] {traj.shape[0]} Frames, {model.nq} qpos -- Endlosschleife (Fenster schliessen zum Beenden)")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            for q in traj:
                if not viewer.is_running():
                    break
                data.qpos[:] = q
                mujoco.mj_forward(model, data)
                viewer.sync()
                time.sleep(dt)


if __name__ == "__main__":
    main()
