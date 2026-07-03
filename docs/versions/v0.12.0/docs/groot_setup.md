# NVIDIA GR00T N1.7 Setup — Anforderungen & Deployment auf H2

> **Status:** Anforderungen & Anleitung für die GR00T-Integration (Zielarchitektur)  
> **Quellen:** NVIDIA Isaac-GR00T (API-geprüft 2026-06-30), Unitree Repos, NVIDIA Hardware-Doku.  
> **Verwandte Dateien:** `docs/roadmap_groot.md` (Zielarchitektur), `docs/dev_environment.md` (Stufen A/B/C Übersicht), `docs/sdk_reference.md` (Unitree H2 API)

---

## ⚠️ Zentrale Einschränkung: Linux + CUDA erforderlich

**GR00T läuft AUSSCHLIESSLICH auf Linux mit NVIDIA-GPU.** Der Windows-Entwicklungsrechner oder die H2-EDU-CPU reichen nicht aus.

- **Training/Fine-Tuning:** Ubuntu 22.04 + NVIDIA-Treiber + CUDA 12.6+ + High-Power-GPU (40+ GB VRAM)
- **Deployment:** Ubuntu 22.04 + Jetson AGX Thor (auf H2 EDU) + CUDA 12.6/13.0 + TensorRT
- **Gegenwärtiger Projektstand (Stufe A):** Keine GPU, kein GR00T erforderlich — läuft auf Windows/Linux

Die nachfolgenden Schritte beschreiben die Umgebung **für späteren Ausbau**. Die Vorbereitungs-Artefakte (Modality-Config, Exporter) sind aber bereits im Repo und plattformneutral.

---

## 1. Hardware-Anforderungen

### Fine-Tuning (Trainings-Cluster)

| Hardware | Empfehlung | Minimum | Kontext |
|---|---|---|---|
| **GPU** | 4–8× H100 / RTX Pro 6000 / A100 | 1× GPU ≥ 40 GB VRAM | Paralleles Multi-GPU-Training emfohlen |
| **VRAM pro GPU** | 80+ GB | 40 GB | Full-Scale braucht volle Gradienten |
| **CPU** | Intel Xeon / AMD EPYC | — | Datenlade-Bottleneck; ≥32 Cores empfohlen |
| **RAM gesamt** | 512+ GB | 128 GB | Datensatz-Caching |
| **Speicher** | NVMe-Raid (2+ TB) | SSD ≥500 GB | Datensatz + Checkpoints |
| **CUDA** | **12.8** (x86_64 dGPU) | 12.6+ | Exakte Version je Plattform; siehe Tabelle 2 |
| **Python** | **3.10** (x86_64) | 3.10 | GR00T-Test mit 3.10.15 |
| **OS** | Ubuntu 22.04 LTS | — | Andere Linuxe: CUDA-Unterstützung prüfen |

**Trainingsdauer:** Projekt-abhängig (Datenmenge, Hyperparameter, Hardware). NVIDIA GR00T-Beispiele mit kleinen Demo-Datensätzen (z.B. `demo_data/cube_to_bowl_5`) trainieren in Stunden; größere Datensätze Tage bis Wochen. **Exakte Dauer gegen aktuelle NVIDIA-Doku prüfen.**

### Inferenz / Deployment (auf H2 EDU)

| Plattform | GPU | VRAM | Modell-Format | Inferenz-Rate | Latenz | Einsatz |
|---|---|---|---|---|---|---|
| **Jetson AGX Thor (optimal)** | 128 GB shared | 128 GB | PyTorch Eager | ~6.9 Hz | ~145 ms | On-Roboter Basis |
| **Jetson AGX Thor** | 128 GB shared | 128 GB | **TensorRT** | **~10.7 Hz** | **~93 ms** | ✓ Produktions-Standard |
| H100 PCIe | 80 GB | 80 GB | TensorRT | ~30+ Hz | ~33 ms | Laborumgebung |
| RTX Pro 6000 | 48 GB | 48 GB | TensorRT | ~20 Hz | ~50 ms | Laborumgebung |
| H2 EDU CPU-only | — | — | — | — | — | **NICHT geeignet** (Fallback: TeachReplayPlanner) |

**Minimum zum produktiven Betrieb:** Jetson AGX Thor mit TensorRT → ~10,7 Hz (reicht für typische Manipulationsaufgaben mit 10 Hz Regelschleife).

**Fallback ohne Erfolg:** Arm-Steuerung fällt zurück auf `ScriptedPolicy` (Teach-&-Replay, CPU-basiert).

---

## 2. Software & Plattform-Matrix

### Install-Strategie nach Plattform

| Plattform | CUDA | Python | Install-Methode | Video-Backend | Special |
|---|---|---|---|---|---|
| **dGPU x86_64** (Training/Lab) | **12.8** | **3.10** | `uv sync --python 3.10` | FFmpeg + torchcodec | Flash-Attn nötig |
| **Jetson Orin** (alt) | 12.6 | 3.10 | `pip install -e .` in venv | torchcodec | Optional TensorRT |
| **Jetson Thor** (neu, H2 EDU) | **13.0** | **3.12** | `pip install -e .` in venv | torchcodec | **Triton-Patch** (s.u.) |
| **DGX Spark** | 13.0 | 3.12 | `pip install -e .` in venv | torchcodec | **Triton-Patch** (s.u.) |

### Abhängigkeiten (quer)

- **FFmpeg:** `libavformat`, `libavcodec` (H.264) — einziges Video-Dekodierungs-Backend von GR00T
- **PyTorch:** ≥2.7 (mit CUDA-spezifischen Wheels)
- **flash-attn:** Für CUDA 12.x Plattformen erforderlich
- **TensorRT:** Optional für Inferenz (stark empfohlen für Deployment wegen ~3× Speedup)
- **torchcodec:** Video-Dekodierung; lädt zur Laufzeit

### Installation — Schritt für Schritt

#### x86_64 dGPU (Training/Lab, CUDA 12.8, Python 3.10)

```bash
# System-Dependencies
sudo apt-get update && sudo apt-get install -y \
  build-essential cmake ffmpeg libavformat-dev libavcodec-dev \
  libavutil-dev libswscale-dev libtorch-dev git

# NVIDIA-Treiber + CUDA 12.8 (falls noch nicht instaliert)
# Siehe: nvidia.com/Download/driverDetails.aspx oder CUDA Toolkit Installer

# GR00T im venv
git clone https://github.com/NVIDIA/Isaac-GR00T.git
cd Isaac-GR00T

# Mit `uv` (schneller, empfohlen):
uv sync --python 3.10
source .venv/bin/activate

# ODER: Mit `pip` (fallback):
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[train]"

# Optional: TensorRT für später
pip install tensorrt  # Nach Installation prüfen: pip show tensorrt
```

**Verifikation:**
```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Version: {torch.version.cuda}')"
python -c "import gr00t; print(gr00t.__version__)"
ffmpeg -version | head -n1  # sollte H.264 enthalten
```

#### Jetson Thor (H2 EDU, CUDA 13.0, Python 3.12)

```bash
# System-Dependencies (auf Thor: Ubuntu 22.04 mit JetPack)
sudo apt-get update && sudo apt-get install -y \
  build-essential cmake ffmpeg libavformat-dev libavcodec-dev \
  libavutil-dev libswscale-dev git python3.12 python3.12-venv

# GR00T im venv
git clone https://github.com/NVIDIA/Isaac-GR00T.git
cd Isaac-GR00T
python3.12 -m venv .venv
source .venv/bin/activate

# **Triton-Patch für CUDA 13.0** (PFLICHT vor pip install)
bash scripts/deployment/patch_triton_cuda13.sh

# Dann Installation
pip install --upgrade pip
pip install -e ".[deploy]"

# TensorRT (meist schon in JetPack enthalten)
pip install tensorrt  # Oder: nutze system-TensorRT
```

**Verifikation:**
```bash
python -c "import torch; print(f'CUDA Compute: {torch.cuda.get_device_capability(0)}')"
python -c "import gr00t; print(gr00t.__version__)"
```

---

## 3. H2 als NEW_EMBODIMENT

### Problem: H2 ist nicht vorgebaut

GR00T N1.7 wird mit Basis-Checkpoints ausgeliefert für:
- **REAL_G1** (Unitree G1) ← im Basis-Checkpoint `nvidia/GR00T-N1.7-3B` belegt
- **REAL_R1-Pro-Sharpa** (Research-Roboter)

Der **H2 EDU ist NICHT vorkonfiguriert**. Wir müssen ihn als `NEW_EMBODIMENT` einbringen:

1. **H2-Kinematik definieren** (URDF, Mesh)
2. **Modality-Config erstellen** (Sensoren, Action-Space)
3. **Teleop-Daten sammeln** (menschliche Demonstrationen)
4. **Fine-Tuning durchführen** (GR00T lernt H2-spezifische Bewegungen)

### Modality-Config — Struktur

Unsere Vorlagen liegen unter `groot/`:

- **`groot/h2_modality_config.py`** — H2-spezifische Sensoren & Action-Space-Definition
- **`groot/meta_modality.example.json`** — Beispiel-Metadaten-Struktur (GR00T-LeRobot-v2-Format)

#### H2 Joint-Mapping (aus H2 SDK)

| Gelenke | Indizes | Details |
|---|---|---|
| **Beine** | 0–11 | Left Ankle/Knee/Hip (PR/AB), Right Ankle/Knee/Hip |
| **Taille** | 12–14 | WaistYaw, WaistRoll, WaistPitch |
| **Linker Arm** | 15–21 | Shoulder (Pitch/Roll), Elbow, Wrist (Pitch/Roll/Yaw), Hand |
| **Rechter Arm** | **22–28** | ← **Relevant für Lader: rechter Arm Pick/Place** |

#### Modality-Config Beispiel

```python
# groot/h2_modality_config.py
from gr00t.configs.data.modality_config import ModalityConfig

h2_modality_config = ModalityConfig(
    name="h2_new_embodiment",
    input_modalities={
        "image": {
            "shape": (480, 640, 3),  # RGB von Head-Kamera
            "dtype": "uint8",
            "frequency_hz": 10
        },
        "proprioception": {
            "keys": ["joint_state_29d", "gripper_state"],
            # 29 Gelenke (0-28) + Greifer
            "frequency_hz": 50
        }
    },
    output_modalities={
        "action": {
            "action_keys": ["right_arm", "gripper"],  # nur rechter Arm
            "right_arm": {
                "joint_indices": [22, 23, 24, 25, 26, 27, 28],  # rechte Arm-Gelenke
                "action_range": [-1.5, 1.5],  # rad
                "velocity_limit": 0.5  # rad/s
            },
            "gripper": {
                "action_range": [0, 1],  # 0=offen, 1=geschlossen
            }
        }
    },
    # Normalisierungs-Parameter für GR00T-Training
    statistics={
        "proprioception_mean": [...],  # aus Trainingsdaten
        "proprioception_std": [...]
    }
)
```

#### Daten-Format (LeRobot v2)

GR00T erwartet Teleop-Daten im **LeRobot v2 Format** mit H.264-Video:

```
my_h2_dataset/
├── meta/
│   └── modality.json         # ← Link zu h2_modality_config
├── videos/
│   ├── episode_0.mp4         # RGB 480×640 H.264, 10 Hz
│   ├── episode_1.mp4
│   └── ...
├── observations/
│   ├── episode_0.npy         # proprioception (29 Gelenke + Greifer)
│   └── ...
└── actions/
    ├── episode_0.npy         # Action-Vektor (7 Arm-Gelenke + 1 Greifer)
    └── ...
```

### Datenerfassung mit `xr_teleoperate`

**Quelle:** `github.com/unitreerobotics/xr_teleoperate` (Unitree)

```bash
# H2 + VR-Headset (Apple Vision Pro / Meta Quest 3)
python -m xr_teleoperate \
    --robot-type h2 \
    --task-name pick_place \
    --output-dir ./h2_teleop_data \
    --format lerobot_v2
```

Output: GR00T-kompatibler LeRobot-v2-Datensatz.

**Datenmenge:** NVIDIA nennt für Imitation Learning grob **50–200 Episoden** als Startpunkt. Exakte Anforderung für H2 → **gegen aktuelle NVIDIA-Doku prüfen.**

---

## 4. End-to-End-Workflow

Workflow mit Stufen-Bezügen zu `docs/roadmap_groot.md`:

### Stufe 1: Teleop-Datenerfassung

**Input:** H2 EDU (mit VR-Controller/Suit), Induktions-Härtemaschine (Testziel)  
**Output:** Trainings-Datensatz im GR00T-LeRobot-v2-Format

1. Setup `xr_teleoperate` (s.o.)
2. Operator steuert H2 per Controller/VR-Suit
3. Demonstrationen: Pick Induktor, Place in Maschine, Remove, Place in Rack
4. Rohdaten (Video + State) → `lerobot_export.py` (im Repo unter `src/h2_loader/dataset/`)
5. Output: `h2_teleop_dataset/` mit videos/, observations/, actions/, meta/

### Stufe 2: Fine-Tune + Sim-Validierung

**Input:** Trainings-Datensatz, H2-Modality-Config  
**Output:** Trainierter GR00T-Checkpoint, Validierungs-Metriken

```bash
# 1. Modality-Config registrieren
python -c "from groot.h2_modality_config import h2_modality_config; register(h2_modality_config)"

# 2. Fine-Tuning starten (auf Multi-GPU-Cluster)
bash examples/finetune.sh \
    --config-name h2_new_embodiment \
    --data-path ./h2_teleop_dataset \
    --output-dir ./checkpoints/groot_h2_v1 \
    --epochs 100
```

**Hyperparameter:** Projekt-abhängig. NVIDIA-Defaults im Repo.

**Sim-Validierung** (mit `unitree_sim_isaaclab`):

```bash
# Test-Szenarien: Pick, Place, Induktor-Wechsel
python examples/validate_in_sim.py \
    --checkpoint ./checkpoints/groot_h2_v1 \
    --task pick_place \
    --episodes 50
# Erfolgsquote als Qualitätskriterium (Ziel: möglichst hoch)
```

### Stufe 3: Deployment auf Jetson Thor mit TensorRT

**Input:** Trainierter Checkpoint, Thor-Hardware  
**Output:** Produktions-Ready GrootPolicy, integriert in h2_loader

```bash
# 1. TensorRT-Optimization
python examples/export_tensorrt.py \
    --checkpoint ./checkpoints/groot_h2_v1 \
    --output ./checkpoints/groot_h2_v1_tensorrt.plan \
    --precision fp16

# 2. Integration in h2_loader
# → Neue Klasse `GrootPolicy` unter `motion/`
# → Safety-Clamping pro Schritt (Workspace, Velocity, Force)
# → Fallback-Logik zu ScriptedPolicy bei Fehler
```

**Real-World Testing:** Erste Läufe unter Beaufsichtigung, Performance-Messung.

---

## 5. Sicherheit — kritisch

Eine gelernte Policy ist **nicht-deterministisch**. Sie kann überraschende Aktionen erzeugen:

- Den Arbeitsraum verlassen
- Geschwindigkeits-Grenzen überschreiten
- Spannvorrichtung beschädigen
- Greifer quetschen

### Sicherheits-Architektur (unveränderbar)

1. **SafetySupervisor bleibt Grundlage** (`docs/safety_concept.md`)
   - Hardwired Sicherheits-SPS (E-Stop, Schutzfeld, Personenzugang)
   - Diese Software-Schicht kann die Hardware-Safety nicht überschreiben

2. **Policy-Output-Clamping (per Schritt)**
   ```python
   action = policy.predict(observation)          # GR00T liefert Aktion
   action = clamp_to_workspace(action, bounds)   # Arbeitsraum-Grenzen
   action = clamp_velocity(action, max_vel=0.3)  # m/s Limit
   action = clamp_forces(action, max_force=50)   # N Greifer-Limit
   send_to_arm(action)
   ```

3. **Watchdog-Timeout**
   Falls GR00T-Inferenz > 200 ms dauert → Arm auf Damping, Skill bricht ab

4. **Fallback bei Fehler**
   GR00T-Checkpoint lädt nicht / Inferenz crasht / Safety-Clamping triggert → `ScriptedPolicy`

**Wichtig:** Dies ist eine **funktionale Schutzschicht**, keine Sicherheitsarchitektur im funktional-sicheren Sinne (IEC 61508). Die echte Sicherheit liegt in hardwired Systemen.

---

## 6. Integrations-Checkpoint im h2_loader

```python
# motion/base.py
class PolicyInterface:
    """Abstract: Input: RGB + Proprioception → Output: Gelenkwinkel"""
    def predict(self, observation, goal=None) -> Action:
        raise NotImplementedError

# motion/groot_policy.py (neu)
class GrootPolicy(PolicyInterface):
    def __init__(self, checkpoint_path: str, device: str = "cuda"):
        self.model = load_groot_checkpoint(checkpoint_path)  # TensorRT oder Eager
        self.tokenizer = GR00TTokenizer()
    
    def predict(self, observation, goal=None) -> Action:
        # RGB + Proprioception normalisieren
        # Durch GR00T-Encoder
        # Trajectory dekodieren → nächsten Schritt extrahieren
        # Clamping (Workspace, Velocity, Force)
        # Zurückgeben
        ...

# app.py (Composition Root)
if config.motion.policy_backend == "groot":
    policy = GrootPolicy(
        checkpoint_path=config.groot.checkpoint,
        device=config.groot.device
    )
elif config.motion.policy_backend == "scripted":
    policy = ScriptedPolicy(teach_replay_planner)

motion_planner = PolicyMotionPlanner(policy)
```

**Effekt:** Skill-Code ändert sich nicht — `move_to(arm, pose_name)` läuft weiterhin, delegiert aber an die Policy.

---

## 7. Offene Punkte — gegen aktuelle NVIDIA-Doku zu prüfen

1. **Exakte H2-Embodiment-Definition**
   - URDF/Mesh des H2 EDU akzeptiert von GR00T? (Unitree hat ihn nicht freigegeben.)
   - Modality-Config-Template für Humanoids verfügbar?
   - Joint-Naming-Konvention, Gelenkausgaben-Formate?

2. **Lizenzbedingungen & Commercial Deployment**
   - Apache-2.0 des Basis-Checkpoints erlaubt Commercial Deployment?
   - Fine-Tuning-Daten: Proprietary-Datensätze erlaubt oder Datenschutz-Meldung nötig?

3. **Reale Inferenzfrequenz auf AGX Thor**
   - Verifizierung: ~10,7 Hz TensorRT wie dokumentiert? Unter Last?
   - Jitter / Varianz?
   - Speicher-Overhead (Model + Buffers) in 128 GB?

4. **Whole-Body vs. Arm-Only**
   - GR00T lernt typisch Ganzkörper-Policy. Wie kapselt man „Balance halten, nur Arme bewegen"?
   - Gewichtungs-Masking im Decoder vorhanden?

5. **Datenmenge für H2-Erfolgsquote**
   - Bisherige GR00T-Experimente: G1, R1-Pro. Lektionen für H2?
   - Erwartete Datenmenge für 80%+ Erfolgsquote?

6. **Teleop-Datenformat & Normalisierung**
   - `xr_teleoperate` Output zu LeRobot v2 exakt verifizieren?
   - Normalisierungs-Statistiken (Mean/Std) wie korrekt erfassen?

---

## Referenzen

**NVIDIA Isaac-GR00T:**
- Repository: `github.com/NVIDIA/Isaac-GR00T` (Branch: main, N1.7)
- Basis-Checkpoint: `nvidia/GR00T-N1.7-3B` (HuggingFace)
- Guides: `docs/finetune_new_embodiment.md`, `docs/data_preparation.md`, `docs/hardware_recommendation.md`, `docs/real_world_deployment.md`
- Skripte: `examples/finetune.sh`, `examples/export_tensorrt.py`, `examples/validate_in_sim.py`

**Unitree H2 + GR00T Integration:**
- `unitree_sdk2_python` — H2 Control via DDS
- `xr_teleoperate` — Teleop-Datenerfassung
- `unitree_sim_isaaclab` — Sim-Validierung
- `unitree_lerobot` — LeRobot v2 Integration

**Unsere Architektur:**
- `docs/roadmap_groot.md` — Zielarchitektur, Phasenplan
- `docs/dev_environment.md` — Stufe A/B/C Übersicht
- `docs/sdk_reference.md` — H2 SDK Details
- `docs/safety_concept.md` — Safety-Supervision

---

**Gültig ab:** 2026-06-30  
**Nächste Überprüfung:** Nach Abschluss von Stufe 1 (Teleop-Datenerfassung)  
**Hinweis:** Private-Modus (kein EMA-Branding)
