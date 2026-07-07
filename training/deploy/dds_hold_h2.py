"""dds_hold_h2.py -- Ganzkoerper-Halteregler fuer den H2 im DDS-Twin.

Sendet ueber DDS (rt/lowcmd, unitree_hg-IDL) einen Positions-Sollwert (Stehpose)
fuer ALLE 31 Aktuatoren mit PD-Verstaerkungen; der Twin (unitree_mujoco-Bridge)
rechnet daraus die Gelenkmomente. Damit uebernimmt die Anwendungsseite die
Ganzkoerper-Kontrolle des H2 im Twin -- der erste Beweis, dass `h2_loader`
(gleiche unitree_sdk2py/unitree_hg-Schnittstelle wie `hal/drivers/unitree_sdk_driver.py`)
den Physik-Twin kommandiert (LowCmd -> Twin), nicht nur Arme.

WICHTIG (verifizierter Befund, ADR-0008 / v0.18.0): Ein rein positionsgeregelter
H2 ist ein instabiles Gleichgewicht -- er FOLGT den Sollwinkeln (das beweist die
Kommando-Autoritaet), haelt die Balance aber nicht dauerhaft (kippt nach einigen
Sekunden). Robustes Stehen/Gehen liefert erst die RL-Policy (Locomotion-Backend).
Dieser Regler dient dem Nachweis des DDS-Steuerpfads, nicht als Balanceregler.

Aktuator-Reihenfolge (verifiziert): 0-5 linkes Bein (hip_pitch,hip_roll,hip_yaw,
knee,ankle_roll,ankle_pitch), 6-11 rechtes Bein, 12-14 Taille, 15-28 Arme, 29-30 Kopf.

Aufruf (auf ematalos, Domain 1 / iface lo, parallel zum Twin-Runner):
    python dds_hold_h2.py [dauer_sekunden]
"""
from __future__ import annotations

import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_
from unitree_sdk2py.utils.crc import CRC

NUM_MOTOR = 31
DOMAIN_ID = 1
IFACE = "lo"

# Stehpose je Aktuator (H2-Knoechelreihenfolge roll VOR pitch), leichte Kniebeuge.
_LEG = [-0.3, 0.0, 0.0, 0.6, 0.0, -0.3]
TARGET = _LEG + _LEG + [0.0] * 3 + [0.0] * 14 + [0.0] * 2  # 6+6+3(Taille)+14(Arme)+2(Kopf)=31
assert len(TARGET) == NUM_MOTOR

# PD-Verstaerkungen je Aktuator: Beine/Taille steif, Arme weicher, Kopf leicht.
_KP_LEG = [150.0, 150.0, 150.0, 200.0, 80.0, 80.0]
_KD_LEG = [4.0, 4.0, 4.0, 5.0, 4.0, 4.0]
KP = _KP_LEG + _KP_LEG + [150.0] * 3 + [40.0] * 14 + [10.0] * 2
KD = _KD_LEG + _KD_LEG + [4.0] * 3 + [2.0] * 14 + [1.0] * 2


def main() -> None:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 35.0

    ChannelFactoryInitialize(DOMAIN_ID, IFACE)
    pub = ChannelPublisher("rt/lowcmd", LowCmd_)
    pub.Init()
    crc = CRC()

    cmd = unitree_hg_msg_dds__LowCmd_()
    for i in range(NUM_MOTOR):
        cmd.motor_cmd[i].mode = 1
        cmd.motor_cmd[i].q = TARGET[i]
        cmd.motor_cmd[i].dq = 0.0
        cmd.motor_cmd[i].kp = KP[i]
        cmd.motor_cmd[i].kd = KD[i]
        cmd.motor_cmd[i].tau = 0.0

    print(f"[hold] sende Ganzkoerper-Stehpose ueber rt/lowcmd ({NUM_MOTOR} Motoren, "
          f"Domain {DOMAIN_ID}/{IFACE}), {duration:.0f}s @ 200 Hz")

    t0 = time.time()
    n = 0
    while time.time() - t0 < duration:
        cmd.crc = crc.Crc(cmd)
        pub.Write(cmd)
        n += 1
        time.sleep(0.005)  # 200 Hz
    print(f"[hold] fertig -- {n} LowCmd-Pakete gesendet.")


if __name__ == "__main__":
    main()
