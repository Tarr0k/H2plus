# SDK-Referenz (Unitree H2) — geerdet an den echten Beispielen & der offiziellen Doku

> Quelle: `github.com/unitreerobotics` (per API geprüft, 2026-06-29) + offizielle H2-Doku
> (`support.unitree.com`, via Browser-Extension extrahiert → `docs/unitree_docs/`). Diese Datei hält die
> **realen** API-Namen/Muster fest, an denen die heutigen Stubs (`UnitreeSdkDriver`, `OnboardLocomotion`,
> `MujocoSimDriver`) auf dem Zielsystem ausgebaut werden. Nichts hier wird zur Laufzeit ausgeführt.

## ⚠️ Korrekturen aus der offiziellen Doku (2026-06-29)

1. **Es gibt KEIN Modell „H2 Plus".** Unitree listet H1, G1, **H2**, R1, G1-D. Vom H2 zwei Varianten:
   Standard **H2** und **H2 EDU**. Der Projekt-/Repo-Name „H2plus" ist unsere interne Bezeichnung, nicht
   das Produkt. In der Doku/Code daher korrekt: **Unitree H2 (EDU)**.
2. **Secondary Development braucht die H2 EDU.** Standard-H2 erlaubt **keine** Eigenentwicklung; SDK-Zugang
   + geschickte Hände (Dexterous Hand) sind **EDU-exklusiv**. → Unser gesamter SDK-Ansatz setzt eine
   **H2 EDU** voraus (Beschaffungs-/Machbarkeitsfaktor). Der Pneumatikgreifer ist davon unabhängig.
3. **Onboard-Compute (real):** PC1 = Intel **i5** (Motion-Control, gesperrt); optional PC2/3/4 = Intel **i7**
   bzw. **Jetson Thor** (nur EDU nimmt High-Power-Module auf). Die früher genannten „Blackwell-GPU/128 GB"
   stammten aus einer unzuverlässigen Produktseiten-Abfrage und sind hier **nicht** belegt — entspricht
   am ehesten dem optionalen Jetson Thor auf der EDU.
4. **Debug-Modus ist Pflicht für SDK-Steuerung:** Beim Einschalten startet das Motion-Control-Programm
   automatisch und sendet Zero-Velocity-Befehle. Ohne **Debug-Modus** → Befehlskonflikte/Zittern.
   Fernbedienung: aktivieren **L2+R2**, bestätigen **L2+A**, Notfall-Damping **L2+B**.
   Betriebsmodi: Zero-Torque, Damping, Ready, Motion, Continuous Walking, Standing, Debug.
5. **Parallelmechanismus:** Knöchel und Taille nutzen einen Parallelmechanismus mit zwei Steuermodi
   **PR** und **AB** (erklärt die Doppelbenennung `LeftAnklePitch/LeftAnkleB`, `LeftAnkleRoll/LeftAnkleA`
   im `H2JointIndex`).
6. **DDS-Topics/IDL:** `rt/lowcmd` (Low-Level-Steuerung), `rt/lowstate` (IMU/Motoren). IDL-Strukturen:
   `LowCmd_`, `LowState_`, `IMUState_`, `MotorCmd_`, `MotorState_` (humanoide `unitree_hg`-Familie).

## Relevante Repos

| Repo | Zweck für uns |
|---|---|
| `unitree_sdk2_python` | **Primär** — Python-Anbindung (Locomotion, Low-Level, Arm). Beispiele unter `example/h2/`. |
| `unitree_sdk2` (C++) | Referenz-SDK; gleiche API-Semantik. |
| `unitree_mujoco` | Simulator, **gleiche DDS-Schnittstelle** → Sim-to-Real per Netzwerk-Interface-Wechsel. |
| `unitree_dds_wrapper` | DDS-Vereinfachung. |
| `unilidar_sdk2` + `point_lio_unilidar` | **Lokalisierung/Odometrie (L2-LiDAR)** — Baustein für die Navigationslücke (siehe unten). |
| `unitree_ros2` | ROS2-Integration (Alternative für Nav/MoveIt2). |
| `unitree_sim_isaaclab`, `unitree_lerobot`, `xr_teleoperate` | KI-Greifen-Pfad (späterer Ausbau). |
| `dex1_1_service`, `dfx_inspire_service`, `linker_hand_service` | Greifer-/Hand-Services (RS485/USB) — falls je Mehrfingerhand. |

## Locomotion — `LocoClient` (echte API)

`example/h2/high_level/h2_loco_client_example.py`:

```python
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient

ChannelFactoryInitialize(0, "enp3s0")   # 0 = real (Ethernet); Sim: ChannelFactoryInitialize(1, "lo")
client = LocoClient(); client.SetTimeout(10.0); client.Init()
client.Start(); client.StandUp()         # FSM hochfahren (Pflicht vor Bewegung)
client.Move(vx, vy, omega)               # Geschwindigkeitsbefehl
client.SetVelocity(vx, vy, omega, duration)
client.StopMove(); client.Damp(); client.ZeroTorque()
client.GetFsmId()/GetFsmMode()/SetFsmId(id)/SwitchMoveMode(bool)/SetSpeedMode(mode)
```

### ⚠️ Velocity-/FSM-basiert — KEIN Wegpunkt-Fahren
Der Onboard-Controller liefert **Geschwindigkeitsbefehle** (`Move`/`SetVelocity`) und FSM-Zustände —
**kein** „fahre zu Position/Station X". Unser `LocomotionInterface.move_to(station)` ist als *Interface*
korrekt, aber die **Onboard-Implementierung kann das nicht allein**:

> `move_to(station)` braucht zusätzlich **Lokalisierung + Pfad-/Regelschicht** (Ist-Pose → Soll-Pose →
> `Move(vx,vy,ω)` als Closed Loop). Bausteine dafür: **`unilidar_sdk2` + `point_lio_unilidar`** (LiDAR-
> Odometrie) oder **`unitree_ros2` + Nav2**. Solange diese Schicht fehlt, ist `OnboardLocomotion` nur
> ein Platzhalter, der die FSM-/Velocity-Befehle kapseln, aber nicht autonom navigieren kann.

## Low-Level / Arme (Humanoid)

`example/h2/high_level/h2_arm_sdk_dds_example.py`, `example/h2/low_level/h2_ankle_swing_example.py`:

```python
from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_   # Humanoide: unitree_hg (NICHT unitree_go)
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.utils.thread import RecurrentThread
```

- **`H2JointIndex`: 29 Gelenke** (0–11 Beine, 12–14 Taille `WaistYaw/Roll/Pitch`, 15–21 linker Arm,
  22–28 rechter Arm) — deckt sich mit `unitree_h2_dokumentation.md`. Pro Gelenk: `kp`, `kd`, `q`, `dq`, `tau`.
- **Arm-only** über `arm_sdk` (Gewichtungs-Member steuert, wie stark der Arm-Befehl greift) — relevant,
  weil unser Lader v. a. die Arme bewegt, während der Onboard-Regler Stand/Balance hält.
- Low-Level-Schreiben braucht **CRC** + Hochfrequenz-Loop via **`RecurrentThread`**.

## FSM-Hochfahrsequenz
Vor jeder Bewegung: `Start` → `StandUp` (ggf. `SetFsmId`). Das sollte unser `Robot.connect()` /
`UnitreeSdkDriver.connect()` auf dem Zielsystem abbilden (heute Stub).

## Sim-to-Real
`unitree_mujoco` nutzt dieselbe DDS-API. Einziger Unterschied im Code:
`ChannelFactoryInitialize(1, "lo")` (Sim, Loopback, domain_id=1) vs. `ChannelFactoryInitialize(0, "enp3s0")`
(real, Ethernet, domain_id=0). Das ist der Punkt, an dem `MujocoSimDriver` und `UnitreeSdkDriver`
auf dem Zielsystem zusammenlaufen.

## Mapping auf unsere Stubs (Ausbau auf dem Zielsystem)

| Unser Stub | Reale Anbindung |
|---|---|
| `hal/drivers/unitree_sdk_driver.py` | `ChannelFactoryInitialize`, `unitree_hg` `LowCmd_/LowState_`, `H2JointIndex`, CRC, `RecurrentThread`; FSM `Start→StandUp`. |
| `hal/locomotion/onboard_locomotion.py` | `LocoClient` (`Init/Start/StandUp/Move/SetVelocity/StopMove`); `move_to` zusätzlich über Lokalisierung+Pfad. |
| `hal/drivers/mujoco_sim_driver.py` | gleiche API, `ChannelFactoryInitialize(1,"lo")`. |
| `plc/handshake.py` (asyncua) | unabhängig vom Unitree-SDK — OPC-UA-Client zur SPS. |
