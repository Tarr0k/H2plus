# Entwicklungsumgebung — Setup-Anleitung

Drei klar getrennte Stufen. **Das meiste (Stufe A, der aktuelle Projektstand) braucht weder GPU noch
Roboter** und läuft auf Windows wie auf Linux. Ubuntu, GPU und der echte H2 kommen erst bei Stufe B/C.

> Hinweis: Versionsangaben zu GR00T/Isaac (Stufe C) sind Stand 2026-06-30 (aus den Hersteller-Repos) —
> vor Einsatz **gegen die aktuelle NVIDIA-/Unitree-Doku prüfen**.

---

## Stufe A — Dieses Projekt (Stub/Sim) entwickeln

Reicht für den kompletten aktuellen Stand (Gerüst, OPC-UA-UDT, Job-Dispatch, Locomotion, Safety, MachineIo).
Läuft unter **Windows oder Linux**, ohne Hardware.

| Komponente | Version | Zweck |
|---|---|---|
| Python | **3.10+** | Basis |
| Git | — | Repo |
| `py-trees` | >=2.2 | Ablaufsteuerung |
| `pyyaml` | >=6.0 | Config |
| `pytest` (dev) | >=7.4 | Tests |
| `mujoco` (sim, optional) | >=3.1 | spätere Simulation |
| `opcua`, `pymodbus` (plc, optional) | >=0.98 / >=3.6 | SPS-Anbindung |

**Installation (im Repo-Wurzelverzeichnis):**

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .[dev]          # oder: pip install -e ".[dev,sim,plc]"

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

**Prüfen, dass alles läuft:**

```bash
pytest -q                              # erwartet: 96 passed
python -m h2_loader.app --driver sim   # voller Lade-Zyklus in Simulation, Ergebnis=OK
```

Empfohlen: **VS Code** + Python-Extension (oder PyCharm). Mehr ist für Stufe A nicht nötig.

---

## Stufe B — Echter H2-Betrieb (Teach-in / SDK-Steuerung)

Sobald der echte Roboter gesteuert wird. **Nur Linux**, und es **muss ein H2 EDU sein** — der Standard-H2
erlaubt keine Eigenentwicklung (SDK-Zugang ist EDU-exklusiv).

| Komponente | Version / Detail |
|---|---|
| OS | **Ubuntu 22.04 LTS** (20.04 eingeschränkt; Windows/macOS NICHT unterstützt) |
| System-Pakete | `cmake g++ build-essential libeigen3-dev libboost-all-dev libyaml-cpp-dev git python3-pip net-tools` |
| DDS-Middleware | **CycloneDDS 0.10.2** (exakt diese Version) |
| Unitree-SDK | `unitree_sdk2` (C++, Pflicht) + `unitree_sdk2_python` |
| Python | 3.10+, `cyclonedds==0.10.2`, `numpy`, `opencv-python` |
| Simulator | `unitree_mujoco` (gleiche DDS-Schnittstelle → Sim-to-Real per Interface-Wechsel) |
| ROS2 (optional) | Humble — nur falls später Navigation/MoveIt2 |
| Netzwerk | Gigabit-Ethernet; Entwicklungs-PC `192.168.123.99`, H2-Mainboard `192.168.123.161`, PC2 `.162` |

**Grobe Installationsschritte (Details: `docs/sdk_reference.md`):**

```bash
sudo apt-get update && sudo apt-get install -y \
  cmake g++ build-essential libeigen3-dev libboost-all-dev libyaml-cpp-dev git python3-pip net-tools

# CycloneDDS 0.10.2
git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x
cd cyclonedds && mkdir build install && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=../install && cmake --build . --target install && cd ../..

# Unitree SDK (C++ + Python)
git clone https://github.com/unitreerobotics/unitree_sdk2.git
git clone https://github.com/unitreerobotics/unitree_sdk2_python.git
export CYCLONEDDS_HOME=~/cyclonedds/install
pip3 install -e unitree_sdk2_python
pip3 install cyclonedds==0.10.2

# Verbindungstest
ping 192.168.123.161
```

**Wichtig vor jeder SDK-Steuerung:** Fernbedienung in den **Debug-Modus** schalten
(aktivieren `L2+R2`, bestätigen `L2+A`, Notfall-Damping `L2+B`) — sonst kollidiert die SDK-Vorgabe mit dem
automatisch laufenden Motion-Control-Programm (Zittern). FSM-Hochfahren `Start → StandUp`.

---

## Stufe C — GR00T-Pfad (Endziel)

Zwei getrennte Hardware-Rollen: **Training** (starke GPU/Cluster) und **Deployment** (Jetson am Roboter).
Details + Stufenplan: `docs/roadmap_groot.md`, `docs/adr/0007-groot-policy-backend-zielarchitektur.md`.

| Rolle | Hardware | Software |
|---|---|---|
| **Fine-Tuning** | GPU **min. 40 GB VRAM** (empf. 4–8× H100/L40; Full-Scale 8× RTX Pro 6000/DGX) | Ubuntu 22.04, NVIDIA-Treiber, **CUDA 12.6+**, `NVIDIA/Isaac-GR00T` (N1.7, Apache-2.0), LeRobot, Isaac Lab/Sim 5.x |
| **Datenaufnahme** | VR-Headset (Apple Vision Pro / Meta Quest 3 / PICO 4) | `unitreerobotics/xr_teleoperate` |
| **Inferenz/Deploy** | **Jetson AGX Thor** auf dem H2 EDU (~10,7 Hz mit TensorRT, min. 16 GB für Inferenz) | GR00T-Inferenz + **TensorRT** |

Besonderheit: **H2 ist in GR00T `NEW_EMBODIMENT`** (Unitree G1 ist vorgebaut, H2 nicht) → eigenes
Fine-Tuning mit H2-URDF, eigener Modality-Config und Teleop-Daten im GR00T-flavored **LeRobot-v2-Format**.

---

## Was läuft wo — Übersicht

| Stufe | Rechner | GPU nötig? | Roboter nötig? |
|---|---|---|---|
| **A** Stub/Sim (heute) | Windows **oder** Linux | nein | nein |
| **B** Echter H2 | Ubuntu 22.04 | nein (für Steuerung) | **H2 EDU** + Debug-Modus |
| **C** GR00T | Ubuntu + Trainings-GPU; Jetson Thor zum Deploy | **ja** | H2 EDU (Daten + Deploy) |

**Fazit:** Für den aktuellen Projektstand genügt **Python 3.10+ und `pip install -e .[dev]`** auf deinem
Windows-Rechner. Alles Weitere ist stufenweise nachrüstbar.
