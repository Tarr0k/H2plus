# Zielarchitektur: GR00T N1.7 als Policy-Backend für den H2-Lader

> **Status:** Zielrichtung (strategisch); **Datum:** 2026-06-30  
> **Quellen:** github.com/NVIDIA/Isaac-GR00T (N1.7, verifiziert per API), Unitree Repos (`xr_teleoperate`, `unitree_sim_isaaclab`), NVIDIA Hardware-Doku.

## 1. Zweck & Abgrenzung

**GR00T N1.7** ist das **Endziel** für die Erzeugung der Manipulationsaktionen des H2-Laders. Das Ziel ist, vom heutigen **Teach-&-Replay-Ansatz** (v0.6.0) zu einer **gelernten, generalisierten Policy** zu wechseln, die aus Demos verallgemeinern kann.

**Wichtig:** GR00T ersetzt **nur die Aktions-Erzeugung** (Arm-Bewegung: gelernt statt geskriptet). 
Alles andere bleibt **unverändert**:
- Orchestrator und Job-Handshake (ADR-0003: MotionPlannerInterface bleibt)
- Sicherheits-Supervisor und hardwired Safety (ADR-0005)
- Locomotion und Navigations-Logik
- PLC-Handshake (SPS-Türzustand, Spannvorrichtung, Werkstück-Handshake)
- Pneumatik-Greifer-Steuerung

Der heutige Teach-in-Pfad (v0.6.0) ist die **pragmatische Brücke** und bleibt **Fallback** — sofern GR00T ausfällt, kann der Roboter im Teach-Replay-Modus weiterarbeiten.

## 2. Was GR00T N1.7 ist

**Vision-Language-Action Foundation Model** (VLA) von NVIDIA für generalistische Roboter.

- **Modell:** ~3 Milliarden Parameter, bfloat16, Apache-2.0-Lizenz
- **Basis-Checkpoint:** `nvidia/GR00T-N1.7-3B` (auf HuggingFace)
- **Aufbau:** Encoder (Vision + Language) → Diffusion-Policy-Decoder → kontinuierliche Arm-Gelenk-Aktionen
- **Input:** RGB-Beobachtung (Kamera), Propriozeption (aktuelle Gelenkpositionen, optional Sprachbefehl)
- **Output:** Gelenkwinkel-Trajektorie (~200 ms in die Zukunft, im Regelfall 50 Hz Schritt-Raten)

**Relevant für uns:** GR00T ist ein **Manipulations-Policy-Modell**, nicht für Locomotion. Die Arm-Bewegung (Pick/Place/Induktor-Wechsel) ist die Domäne; Fortbewegung bleibt klassisch (Geschwindigkeit, FSM).

## 3. Embodiment-Status — kritisch für H2

### Gegenwärtiger Stand
GR00T N1.7 wurde auf mehreren Roboter-Embodiments vortrainiert:
- **REAL_G1** (Unitree G1) — im Basis-Checkpoint belegt
- **REAL_R1-Pro-Sharpa** — im Basis-Checkpoint belegt
- Weitere humanoide Forschungsroboter

**Posttraining-Tags** (Fine-Tune-Vorlage):
- `UNITREE_G1` (Generic)
- `UNITREE_G1_SONIC`
- Sim-Umgebungen: LIBERO, SimplerEnv

### Der H2-Status: **NICHT vorgebaut**
Der Unitree **H2 EDU ist NICHT als vorkonfiguriertes Embodiment** in GR00T vorhanden. Das heißt:

1. **Keine fertigen Gewichte** für H2-Kinematik, H2-Sensorik (Kamera-Position, Arm-Kalibrierung).
2. **Wir müssen H2 als `NEW_EMBODIMENT` einbringen** — eigenes Fine-Tuning auf eigene Daten und Modality-Konfiguration.

**Konsequenz:** 
- URDF/Mesh des H2 definieren (Gelenkausgaben, Greifer-Geometrie, Kamera-Pose).
- Teleop-Daten von H2 aufnehmen (menschliche Demos mit Controller/Suit; NVIDIA-Repository `xr_teleoperate`).
- Modality-Konfiguration erstellen (welche Sensoren, Sensor-Raten, Action-Raum).
- Fine-Tuning durchführen (mehrere H100/RTX Pro GPUs; genaue Trainingsdauer hängt von Datenmenge/Hardware ab).
- Sim-Validierung gegen echte Zielaufgaben.

Dies ist **nicht trivial**, aber machbar mit dem Basismodell.

## 4. Datenpipeline (vereinfacht)

```
┌─────────────────────────────────────────────────────────────┐
│ Stufe 1: Teleop-Datenerfassung (H2 EDU erforderlich)        │
├─────────────────────────────────────────────────────────────┤
│ xr_teleoperate (Unitree-Repository, Python/ROS2)           │
│ → Menschliche Demonstrationen mit Controller/VR-Suit      │
│   (Operator steuert H2 per Funk; Video + State werden       │
│    gestreamt)                                                │
│ → GR00T-flavored LeRobot v2 Datensatz-Format               │
│   (rgb, proprioception, action je Demo)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stufe 2: Modality-Config + NEW_EMBODIMENT                  │
├─────────────────────────────────────────────────────────────┤
│ gr00t.configs.data.embodiment_configs.register_modality_config
│   - Input:  RGB, Propriozeption (29 Gelenke, IMU)          │
│   - Action: 7 Arm-Gelenke (beide Arme) + Greifer (1 DOF)  │
│   - Frequenz: 10 Hz (Policy-Rückgabe), 50 Hz (Regelschleife)
│ Beispiel: examples/SO100 (Fourier GR1 Humanoid)             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stufe 3: Fine-Tuning (mit 4–8× H100 / RTX Pro 6000)        │
├─────────────────────────────────────────────────────────────┤
│ examples/finetune.sh mit NEW_EMBODIMENT-Konfiguration      │
│ → Trainingsdauer hängt von Datenmenge/Hardware ab         │
│ → Output: trainiertes Checkpoint (für Deployment-Phase)    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stufe 4: Validierung (Isaac Lab / unitree_sim_isaaclab)    │
├─────────────────────────────────────────────────────────────┤
│ Sim-Environement mit H2-Modell:                            │
│ → Test-Szenarien (Pick/Place, Induktor-Wechsel)           │
│ → Erfolgsquote als Qualitätskriterium (Ziel)              │
│ Iterationen bei Bedarf (Daten/Hyperparameter)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Stufe 5: Deployment (Jetson AGX Thor auf H2 EDU)           │
├─────────────────────────────────────────────────────────────┤
│ TensorRT-optimiertes Modell (~1,5–3,3× schneller als Eager)
│ Inferenz-Rate: ~10,7 Hz mit TensorRT (verifiziert)         │
│ Safety-Clamping in jedem Schritt (s.u.)                     │
│ Fallback: TeachReplayPlanner bei Fehler/Timeout            │
└─────────────────────────────────────────────────────────────┘
```

### Tabelle: Daten-Anforderungen

| Phase | Quelle | Format | Volumen | Raten |
|-------|--------|--------|---------|-------|
| Teleop | xr_teleoperate (Operateur + H2 EDU) | GR00T-flavored LeRobot v2 | Projekt-abhängig | RGB, Proprioception (Sensorraten variabel) |
| Modality-Config | NVIDIA Beispiele + eigene URDF | gr00t.configs.data | 1 Konfiguration | — |
| Fine-Tune-Datensatz | Datenerfassung aggregiert | LeRobot v2 | Projekt-abhängig | — |
| Validierung | Sim-Rollouts (Isaac Lab) | Simulation | Projekt-abhängig | — |

---

## 5. Hardware-Voraussetzungen

### A. Fine-Tuning-Hardware
Für das eigentliche Training benötigt:

| Konfiguration | GPU | VRAM | Kontext |
|---|---|---|---|
| Full-Scale | 4–8× H100 / RTX Pro 6000 | Aggregiert (nicht belegt) | Empfohlen für Production; paralleles Training |
| Minimum | 1× GPU mit 40+ GB VRAM | 40+ GB | CUDA 12.6+ erforderlich |

**Trainingsdauer:** abhängig von Datenmenge und Hardware (nicht belegt)

### B. Inferenz/Deployment-Hardware
Auf dem H2 EDU selbst (Jetson AGX Thor):

| Plattform | GPU | VRAM | Modell-Format | Inferenz-Rate | Latenz |
|---|---|---|---|---|---|
| **AGX Thor (H2 EDU optimal)** | 128 GB shared | 128 GB | PyTorch Eager | ~6.9 Hz | ~145 ms |
| **AGX Thor** | 128 GB shared | 128 GB | TensorRT | ~10.7 Hz | ~93 ms |
| H100 PCIe | 80 GB | 80 GB | TensorRT | ~30+ Hz | ~33 ms |
| RTX 6000 | 48 GB | 48 GB | TensorRT | ~20 Hz | ~50 ms |

**Minimum zum Betrieb:** AGX Thor mit TensorRT-Optimization → **~10 Hz**, reicht für die meisten Manipulationsaufgaben (typischer Regeltakt 10 Hz).

**Fallback ohne GPU:** TeachReplayPlanner (heutiger Teach-in Modus, läuft auf H2 EDU CPU).

---

## 6. Integrations-Seam in unsere Architektur

Gemäß ADR-0003 (`MotionPlannerInterface`), werden wir ein neues **`PolicyInterface`** einführen:

```python
# motion/base.py
class PolicyInterface:
    """
    Abstraktes Interface für Arm-Aktions-Policies.
    Input: RGB-Beobachtung + Propriozeption
    Output: Gelenkwinkel-Trajektorie (kontinuierlich oder diskret)
    """
    
    def predict(
        self,
        observation: Observation,  # RGB + Joint-State
        goal: str | None = None     # Optional: "grasp", "place", etc.
    ) -> Action:                    # Gelenkwinkel-Vektor
        """Liefert nächste Aktion(en) für den Arm."""
        raise NotImplementedError
    
    def reset(self):
        """Zurücksetzen von State (z.B. RNN-Hidden-States)."""
        pass
```

### Zwei konkrete Implementierungen

**1. `ScriptedPolicy` (heute)**
```python
class ScriptedPolicy(PolicyInterface):
    """
    Teach-&-Replay Backend (v0.6.0).
    Abgerufene, angelernte Posen sequenziell abspielen.
    """
    def __init__(self, teach_replay_planner: TeachReplayPlanner):
        self.planner = teach_replay_planner
    
    def predict(self, observation, goal=None) -> Action:
        # Nächste Pose aus Teach-DB abholen, zurückgeben
        ...
```

**2. `GrootPolicy` (Zielzustand)**
```python
class GrootPolicy(PolicyInterface):
    """
    GR00T N1.7 Fine-Tuned-Modell für H2 NEW_EMBODIMENT.
    TensorRT-optimiert, läuft auf AGX Thor.
    """
    def __init__(self, checkpoint_path: str, device: str = "cuda"):
        self.model = load_groot_checkpoint(checkpoint_path)  # TensorRT
        self.tokenizer = GR00TTokenizer()
    
    def predict(self, observation: Observation, goal: str | None = None) -> Action:
        # RGB + Proprioception normalisieren
        # Durch GR00T-Encoder
        # Trajectory (200 ms in Zukunft) dekodieren
        # Nächsten Schritt extrahieren, clampen (Safety), zurückgeben
        ...
    
    def reset(self):
        # RNN-State zurücksetzen, falls vorhanden
        pass
```

### Auswahl im Composition Root

```python
# app.py
if config.motion.policy_backend == "scripted":
    policy = ScriptedPolicy(teach_replay_planner)
elif config.motion.policy_backend == "groot":
    policy = GrootPolicy(
        checkpoint_path=config.groot.checkpoint,
        device=config.groot.device
    )

motion_planner = PolicyMotionPlanner(policy)  # Neuer Wrapper: delegiert an Policy
```

**Effekt:** Ein Skill-Code ändert sich **nicht** — benutzt weiterhin `MotionPlannerInterface.move_to(arm, pose_name)`, der sich unter der Haube an die Policy delegiert.

---

## 7. Sicherheit — kritisch

**Eine gelernte Policy ist nicht-deterministisch.** Sie kann überraschende Aktionen erzeugen, die:
- Den Arbeitsraum verlassen
- Geschwindigkeits-Grenzen überschreiten
- Die Spannvorrichtung beschädigen
- Den Greifer quetschen

**Maßnahmen:**

1. **SafetySupervisor bleibt unverändert** (ADR-0005)  
   — hardwired Safety, Schutzfeld, E-Stop, Heartbeat, Personenzugang-Kontrolle.

2. **Policy-Ausgaben werden geclamped (Safety-Clamping)**
   ```python
   # In jedem Schritt vor dem Arm-SDK:
   action = policy.predict(observation)
   action = clamp_to_workspace(action, bounds)      # Arbeitsraum-Grenzen
   action = clamp_velocity(action, max_vel=0.3)    # m/s Sicherheits-Limit
   action = clamp_forces(action, max_force=50)     # N (Greifer-Quetsch-Limit)
   send_to_arm(action)
   ```

3. **Watchdog-Timeout**  
   Falls Policy-Inferenz länger als 200 ms dauert (CPU-Last, GPU-Fehler), wird der Arm auf Damping gesetzt und Skill bricht ab.

4. **Fallback bei Fehler**  
   Falls GR00T-Checkpoint nicht lädt, Inferenz crasht oder Safety-Clamping triggert → sofort zurück zu `ScriptedPolicy`.

5. **Separate Sicherheits-SPS bleibt zwingend**  
   Diese Software-Schicht ist **funktional, nicht sicherheitsgerichtet**. Die echte Sicherheit (Not-Halt, Personenschutz, Bremsgruppen) liegt in der hardwired Sicherheits-SPS und kann von dieser Software nicht überschrieben werden.

---

## 8. Stufenplan bis zur Zielarchitektur

### Stufe 0: Heute (v0.6.0)
- **Teach-&-Replay Backend** läuft in Produktion.
- Fallback-Modus, wenn spätere Stufen ausfallen.
- Keine GR00T, keine Policy-Abstraktionsschicht.

### Stufe 1: Teleop-Datenerfassung
- **H2 EDU Beschaffung** (falls nicht vorhanden).
- **Setup der `xr_teleoperate`-Umgebung** (Unitree-Repository).
- **Sammlung von Daten** (menschliche Demonstrationen an Induktions-Härtemaschine):
  - Operator per Controller/VR-Suit steuert H2.
  - Video + State + Action werden mitgeloggt.
  - Zieldatenformat: GR00T-flavored LeRobot v2.
  - Datenmenge projekt-/aufgabenabhängig, noch festzulegen; GR00T-Beispiele nutzen kleine Demo-Datensätze (z.B. `demo_data/cube_to_bowl_5`), Unitree nennt für Imitation Learning grob 50–200 Episoden — exakte Menge gegen aktuelle Doku prüfen.
- **Output:** Trainings-Datensatz.
- **Fallback:** TeachReplayPlanner bleibt 100% funktional.

### Stufe 2: Fine-Tune NEW_EMBODIMENT + Sim-Validierung
- **Modality-Config für H2 definieren** (Sensoren, Action-Space, Normalisierung).
- **Fine-Tuning-Lauf** auf Cluster mit 4–8× H100 / RTX Pro 6000.
- **Sim-Validierung** gegen Isaac Lab mit H2-Modell:
  - Test-Szenarien: Pick, Place, Induktor-Wechsel.
  - Erfolgsquote als Qualitätskriterium (Ziel: möglichst hoch).
  - Latenz & Stabilität prüfen.
- **Iterationen bei Bedarf** (Daten, Hyperparameter, Architecture).
- **Output:** trainiertes Checkpoint (versioniert).
- **Fallback:** TeachReplayPlanner.

### Stufe 3: Deployment auf Thor mit Safety-Clamping
- **TensorRT-Optimization** des trainierten Checkpoints.
- **Integration `GrootPolicy` in h2_loader** (neue Komponente unter `motion/`).
- **Safety-Clamping-Implementierung** (Workspace, Velocity, Force-Limits).
- **Real-World Testing** auf H2 EDU an echten Induktions-Härtemaschinen:
  - Erste Läufe unter Beaufsichtigung.
  - Performance-Messung (Erfolgsquote, Latenz, Sicherheits-Trigger-Events).
  - Iteratives Tuning.
- **Fallback-Logik** testen (GR00T-Fehler → ScriptedPolicy).
- **Output:** Produktionsreife GR00T-Backend, neben TeachReplayPlanner.
- **Zeitplan:** Stufe 2 muss abgeschlossen sein; Zeitpunkt projektabhängig, noch festzulegen.

---

## 9. Offene Punkte — gegen aktuelle NVIDIA-Doku zu verifizieren

Folgende Punkte erfordern Verifikation mit dem NVIDIA Isaac-GR00T-Team:

1. **Exakte H2-Embodiment-Definition**
   - URDF/Mesh des H2 EDU akzeptiert? (Unitree hat ihn nicht freigegeben.)
   - Modality-Config-Template für Humanoids verfügbar?
   - Joint-Naming-Konvention (29 Gelenke, Arm-Indizes)?

2. **Lizenzbedingungen des Basis-Checkpoints**
   - Apache-2.0 erlaubt Commercial Deployment?
   - Fine-Tuning-Daten: Proprietary oder Datenbank-Meldung nötig?

3. **Reale Inferenzfrequenz auf AGX Thor**
   - Verifizierung: ~10,7 Hz TensorRT (wie dokumentiert)?
   - Jitter / Varianz unter Last?
   - Speicher-Overhead (Model + Buffers)?

4. **Whole-Body vs. Arm-Only**
   - GR00T lernt Ganzkörper-Policy. Wie kapselt man „Balance erhalten, nur Arme bewegen"?
   - Ist Gewichtungs-Masking im Decoder vorhanden?

5. **Datenmenge für H2-Zielleistung**
   - Bisherige GR00T-Experimente: G1, R1-Pro. Lehren für H2?
   - Erwartete Datenmenge für 80%+ Erfolgsquote?

---

## 10. Referenzen

- **NVIDIA Isaac GR00T:** github.com/NVIDIA/Isaac-GR00T (N1.7)
  - Basis-Checkpoint: `nvidia/GR00T-N1.7-3B` (HuggingFace)
  - Guides: `docs/hardware_recommendation.md`, `docs/finetune_new_embodiment.md`, `docs/data_preparation.md`, `docs/policy.md`, `docs/real_world_deployment.md`
  - Fine-Tune-Skript: `examples/finetune.sh`
  - Jupyter Notebooks: `GR00T_inference.ipynb`

- **Unitree Repos für H2:**
  - `unitree_sdk2_python` (Basis-SDK)
  - `xr_teleoperate` (Teleop-Datenerfassung)
  - `unitree_sim_isaaclab` (Simulation für Validierung)
  - `unitree_lerobot` (LeRobot-Integration)

- **Unsere Architektur:**
  - ADR-0003: MotionPlannerInterface
  - ADR-0005: Sicherheitskonzept
  - `docs/sdk_reference.md`: H2-Spezifika
  - `docs/architecture.md`: Schichtenmodell

---

**Gültig ab:** 2026-06-30  
**Nächste Überprüfung:** Nach Abschluss von Stufe 1 (Teleop-Datenerfassung)
