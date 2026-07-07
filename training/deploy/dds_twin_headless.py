"""dds_twin_headless.py -- fuehrt den unitree_mujoco-DDS-Twin OHNE Viewer aus.

Unitrees `unitree_mujoco.py` koppelt die Simulationsschleife an ein
MuJoCo-Viewer-Fenster (`while viewer.is_running()`), was GPU-Rendering (VirtualGL)
braucht. Dieser Runner nutzt dieselbe `UnitreeSdk2Bridge` (DDS <-> Sim), laeuft
aber HEADLESS -- reine CPU-Physik, kein Fenster, keine GPU. So laesst er sich
parallel zu einem laufenden GPU-Training betreiben, ohne es zu bremsen.

Er publiziert `rt/lowstate` und wendet eingehende `rt/lowcmd` auf die Sim an
(genau wie die Original-Bridge) und loggt zusaetzlich sekuendlich die Basis-Hoehe
+ ein paar Beingelenkwinkel aus `mj_data` -- so laesst sich verifizieren, ob ein
externer Regler (z. B. `dds_hold_h2.py` als h2_loader-Stellvertreter) den H2 im
Twin tatsaechlich kommandiert (Gelenke folgen den Sollwerten) und ob er steht.

Aufruf (auf ematalos, im unitree_mujoco/simulate_python-Verzeichnis):
    python dds_twin_headless.py [dauer_sekunden]
"""
from __future__ import annotations

import math
import sys
import time

import mujoco

# config + Bridge stammen aus unitree_mujoco/simulate_python (dieses Skript wird
# von dort ausgefuehrt, siehe --working-directory).
import config
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py_bridge import UnitreeSdk2Bridge


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0

    mj_model = mujoco.MjModel.from_xml_path(config.ROBOT_SCENE)
    mj_data = mujoco.MjData(mj_model)
    mj_model.opt.timestep = config.SIMULATE_DT

    # In die Home-Pose setzen, falls das Modell einen Keyframe hat (sonst faellt
    # der H2 aus der Nullstellung sofort um -- wir wollen den Effekt des Reglers sehen).
    if mj_model.nkey > 0:
        mujoco.mj_resetDataKeyframe(mj_model, mj_data, 0)

    ChannelFactoryInitialize(config.DOMAIN_ID, config.INTERFACE)
    _bridge = UnitreeSdk2Bridge(mj_model, mj_data)  # startet DDS pub/sub-Threads

    print(f"[twin] headless gestartet: {config.ROBOT}, {duration:.0f}s, "
          f"nu={mj_model.nu}, dt={config.SIMULATE_DT}, domain={config.DOMAIN_ID}")

    def grav_z(q):
        qw, qx, qy, qz = q
        return 1.0 - 2.0 * (qw * qw + qz * qz)

    n_steps = int(duration / config.SIMULATE_DT)
    log_every = int(1.0 / config.SIMULATE_DT)  # ~1 s
    for i in range(n_steps):
        mujoco.mj_step(mj_model, mj_data)
        if i % log_every == 0:
            z = float(mj_data.qpos[2])
            gz = grav_z(mj_data.qpos[3:7])
            # linkes Bein-qpos (qpos[7:13]) = hip_pitch,hip_roll,hip_yaw,knee,ankle_roll,ankle_pitch
            leg = [round(float(x), 2) for x in mj_data.qpos[7:13]]
            up = "aufrecht" if gz < -0.5 else "GEKIPPT"
            print(f"  t={i*config.SIMULATE_DT:5.1f}s  z={z:.3f}m  grav_z={gz:+.2f} ({up})  "
                  f"linkes Bein q={leg}")
        time.sleep(config.SIMULATE_DT)

    print("[twin] Ende.")


if __name__ == "__main__":
    main()
