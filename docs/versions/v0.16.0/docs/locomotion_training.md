# H2-Lauf-Training: Strategie und Trainingsplan

> **Status:** Strategie (verifiziert gegen Unitree-Repos und ISaac-GR00T, 2026-07-06)  
> **Quellen:** Unitree RL-Repos (unitree_rl_lab, unitree_rl_gym, unitree_rl_mjlab), NVIDIA Isaac Lab/Sim,  
> H2-SDKs — Details: `docs/sdk_reference.md`, `docs/roadmap_groot.md`, `docs/dev_environment.md`

---

## 1. Zweck & Abgrenzung

**Laufen** im H2-Kontext bedeutet: **Reinforcement-Learning-basierte Locomotion-Policy für die Beingelenke**, 50 Hz Regelfrequenz, trainiert auf GPU, deployed im MuJoCo-Twin oder auf echtem H2.

**Keine fertige H2-Lauf-Policy existiert.** Unitree veröffentlicht RL-Policies nur für G1, H1, H1_2, Go2 und A2 — der H2 EDU ist zu neu. Der H2 muss daher trainiert werden, mit dem Unitree G1 als **Vorlage und Struktur-Referenz**.

**Wichtig: Laufen vs. Manipulation**

- **Locomotion (dieses Dokument):** RL-Policy für 12 Beingelenke, Basis-FSM-Zustände, Geschwindigkeitsziele (vx, vy, ω).
- **Manipulation (Arme, Greifer):** Separat über **Teach-in-Replay** (v0.6.0, heute) oder später **GR00T** (siehe `docs/roadmap_groot.md`).
- **Taille (waist_yaw/roll/pitch):** Teil der Locomotion-Policy (Balance, Torso-Ausrichtung).

Diese Datei behandelt nur Locomotion. Arm-Policies sind ein separater Pfad.

---

## 2. Warum Unitree G1 die beste Vorlage ist

### Vergleich: G1 vs. H1 vs. H2

| Merkmal | **G1** | H1 | H2 (unser Ziel) |
|---------|--------|----|----|
| **Beine (pro Seite, DoF)** | 6 DoF (hip_pitch, hip_roll, hip_yaw, knee, ankle_pitch, ankle_roll) | 5 DoF (kein ankle_roll) | **6 DoF — identisch mit G1** |
| **Arme (pro Seite, DoF)** | 7 (shoulder_pitch/roll/yaw, elbow, wrist_roll/pitch/yaw) | 4 (shoulder_pitch/roll/yaw, elbow; **KEIN Handgelenk**) | **7 — identisch mit G1** |
| **Taille** | 3 (waist_yaw, waist_roll, waist_pitch) | 1 (waist_yaw; **KEINE Roll/Pitch**) | **3 — identisch mit G1** |
| **Gesamt-Gelenke** | 29 (12 Beine + 3 Taille + 14 Arme) | 22 | **29 — identisch mit G1** |
| **Gelenk-Namensschemata** | ✓ Konsistent | ✗ Abweichend | **✓ G1-kompatibel** |
| **G1-RL-Policy vorhanden** | **Ja** (velocity, 12 actions, 47 obs) | Ja, aber andere DoF → schlechter Match | — |

**Resultat:** H2 und G1 haben **exakt die gleiche Gelenkstruktur**. H1 ist kinematisch *unterschiedlich* (nur 1-DoF-Taille, 5-DoF-Beine) → schlechtere Vorlage.

**Gelenknummern (29dof, beide identisch):**
- Beine: 0–11 (6 pro Seite: hip_pitch/roll/yaw, knee, ankle_pitch/roll resp. ankle_pitch/ankle_B und ankle_roll/ankle_A)
- Taille: 12–14 (waist_yaw/roll/pitch)
- Arme: 15–21 (links), 22–28 (rechts)

Diese Entsprechung ist **das Fundament der Übertragung.**

---

## 3. Was übertragbar ist — was nicht

### Übertragbar: Struktur, Config, Reward-Rezeptur

Die G1-Policy kann als **Template** für die H2-Trainings-Konfiguration dienen:

- **Action-Raum:** 12 Beingelenk-Ausgaben (qref) — Topologie identisch.
- **Observation-Raum:** 47 Werte (Propriozeption, IMU, Geschwindigkeit) — Struktur analog.
- **Reward-Funktionen:** Balance, Fortschritt, Energieeffizienz, Glattheits-Regularisierung.
- **Simulator-Config (MJCF/URDF):** Taille-/Gelenk-Limits, Motorgains, Kp/Kd.
- **Frameworke:** IsaacLab, Isaac Gym, MuJoCo.

### **NICHT übertragbar: Gewichte und Gains**

| Parameter | G1 | H2 | Problem |
|-----------|----|----|---------|
| Körpermasse | ~35 kg | ~70 kg | **2× schwerer** → andere Dynamik |
| Höhe | ~1,3 m | ~1,8 m | **längere Hebel** → andere Inertia-Trägheit |
| Motor-Gains (Kp, Kd) | von G1-Hardware | — | **Hardware unterschiedlich** → Neukalibrierung |
| Policy-Gewichte | `g1_locomotion.pt` / `g1_velocity_policy.onnx` | — | **Masse/Hebel/Sensitivität unterschiedlich** |

**Konsequenz:**
- G1-Policy-Gewichte (`.pt` / `.onnx`) können **nicht direkt importiert** werden.
- **Mit H2-URDF neu trainieren** — aber die RL-Konfiguration kopieren und anpassen.
- Gewichte müssen für H2-Masse/Dynamik gelernt werden.

---

## 4. Trainings-Pipeline: A–E

### (A) H2 als Robot im Simulator definieren

**Input:** H2 URDF/MJCF, Gelenkausgaben, Gains.  
**Verweis:** `training/h2_locomotion_deploy.yaml`, `config/robot.sim_mujoco.yaml`

- URDF-Export oder MJCF-Erstellung (H2-Geometrie, Reibung, Motor-Props).
- Gelenk-Limits und Geschwindigkeitsbeschränkungen setzen.
- Motor-Gains (`kp`, `kd`) von H2-Hardware-Doku oder Unitree-Empfehlung.
- Simulator-Umgebung (Boden, Licht, Kamera-Pose).

**Output:** Funktionierendes H2-Modell in IsaacLab/MuJoCo; Sim-to-Real-Tests gegen Stubs erfolgreiche Posen-Rückmeldungen.

### (B) Training auf RTX-GPU

**Hardware-Voraussetzung:** **RTX-Grafikkarte mit RT-Cores** (mindestens RTX 3080, empfohlen RTX 4080 oder H100/L40).

> ⚠️ **Wichtig:** Die vorhandene **NVIDIA Quadro M4000 (Maxwell-Architektur) reicht NICHT** — hat keine RT-Cores und ist für Humanoid-RL zu langsam. Siehe Abschnitt 5 (Hardware).

- Framework-Auswahl: **unitree_rl_lab (IsaacLab)** empfohlen (moderne, fastest Convergence).
- Konfiguration: H2-URDF, Reward-Funktionen (Balance, Forward-Progress, Energy, Smoothness).
- Hyperparameter: von G1-Config übernehmen, für H2-Masse anpassen (z.B. Reward-Gewichtungen für Balance).
- Trainingsdauer: Projekt-abhängig; gegen aktuelle unitree_rl_lab-Doku prüfen (üblicherweise 100 k–1 M steps).

**Output:** Trainiertes Policy-Checkpoint (PyTorch `.pt` oder ONNX `.onnx`).

### (C) Export zu ONNX / TorchScript

**Input:** Trainiertes Checkpoint.

- Export als ONNX (für TensorRT-Optimization) oder `.pt` (für CPU/GPU-Inferenz).
- Normalisierungs-Parameter mitführen (Observation-Scaling).
- Freeze & Test gegen Sim.

**Output:** Deployable Model (`h2_locomotion_policy.onnx` / `h2_locomotion_policy.pt`).

### (D) Sim-Validierung im MuJoCo-Twin

**Hardware:** CPU oder GPU, unitree_mujoco läuft überall.

- H2-Modell im Twin laden (bereits vorhanden; siehe `docs/roadmap_groot.md`).
- Policy laden, Test-Szenarien fahren (Geradeaus, Kurven, Hindernis-Navigation, Stabilitäts-Grenzfälle).
- Erfolgsmetriken: Stabilität, Energie pro Meter, Genauigkeit des Geschwindigkeitszufolgens.

**Output:** Validierte Policy, Ready für Real-World Testing.

### (E) Sim-to-Real und Debugging auf echter Hardware (H2 EDU)

**Voraussetzung:** H2 EDU im Debug-Modus (siehe `docs/sdk_reference.md`).

- Policy lokal auf Development-PC mit H2-SDK testen (über Netzwerk).
- Langsame FSM-Zustände durchlaufen (Standby → Standing → Walking).
- Beobachte: IMU-Stabilität, Motor-Fehler, Sensorabweichungen.
- **Iteratives Tuning:** Gains anpassen, Reward-Anpassungen, ggf. Trainingsdaten korrigieren.

**Output:** Produktive Locomotion-Policy auf H2 EDU oder Sim-Twin.

---

## 5. Framework-Wahl und Hardware-Anforderungen

### Frameworks (RL-Stacks von Unitree)

| Framework | Basis | GPU-Anforderung | Reife | Empfehlung |
|-----------|-------|---|---|---|
| **unitree_rl_lab** | IsaacLab 5.x (NVIDIA) | RTX ab 3080 oder H100 | ✓ Produzieren | ✅ **Erste Wahl** |
| **unitree_rl_gym** | Isaac Gym (älter) | RTX Kepler+ | ⊘ Legacy | Falls kein IsaacLab verfügbar |
| **unitree_rl_mjlab** | MuJoCo | CPU-Tauglich, GPU optional | ✓ Produzieren | GPU-arm, langsamer Humanoid |

**Empfehlung:** **unitree_rl_lab** — moderne API, schnelles Konvergieren, beste Trajectory-Qualität.

### GPU-Anforderungen

#### A. Fine-Tuning (Training)

| Ziel | GPU | VRAM | Trainingsdauer | Kontext |
|-----|-----|------|---|---|
| Minimal (1× RTX 3080) | 1× RTX 3080 | 10 GB | Wochen (sehr langsam) | Nur als letztes Resort |
| Standard (1× RTX 4080) | 1× RTX 4080 | 24 GB | Tage | Einzelne Trainings-Runs |
| Empfohlen (4× H100) | 4–8× H100 / RTX Pro 6000 | Aggregiert | ~24 h (Clusters parallelisieren) | Production Pipelines |

**Minimum:** RTX mit **RT-Cores** (Tensor-Cores + RT-Cores für IsaacLab/IsaacSim Raycast).  
**Nicht geeignet:** Quadro M4000 (Maxwell, kein RT), GTX 1080 Ti (Pascal, kein RT), CPUs für Humanoid-RL.

#### B. Inferenz/Deployment

| Hardware | Modell-Format | Raten | Kontext |
|----------|---|---|---|
| **MuJoCo-Twin (CPU)** | PyTorch `.pt` | ~50 Hz (einfach) | Validierung, Offline |
| **MuJoCo-Twin (GPU)** | ONNX (TensorRT) | ~100 Hz | Echtzeit-Validierung |
| **H2 EDU Jetson Thor** | ONNX (TensorRT-opt.) | ~10.7 Hz | Deployed Policy |
| **H2 EDU CPU only** | PyTorch `.pt` (eager) | ~0,5 Hz | Fallback (sehr langsam) |

**Fazit:** Inferenz ist **CPU-tauglich** — Deployment läuft auch ohne GPU auf dem Jetson (CPU+shared Memory). Training braucht aber RTX.

---

## 6. Lokomotion und GR00T: Getrennte Policies

Siehe `docs/roadmap_groot.md` für GR00T-Endziel (Manipulation).

**Wichtig:** Locomotion (Beine, Laufen) und Manipulation (Arme, Greifer, Werkstücke) sind **unabhängige Policies**:

- **Locomotion-Policy (dieses Dokument):** RL, 12 Beingelenk-Ausgaben, Basis-Fortschritt.
- **GR00T-Manipulation-Policy:** Vision-Language-Action, 15 Arm-+Greifer-Gelenke, Aufgaben-bezogen (Pick, Place, Induktor-Wechsel).

Im Orchestrator (`motion/base.py`, siehe ADR-0003) werden beide über ein gemeinsames `PolicyInterface` genutzt — aber trainiert separat und mit unterschiedlichen Daten.

**G1 ist Vorlage für beides:**
- G1-Locomotion-Policy → H2-Locomotion-Training (dieses Dokument).
- G1 als Embodiment in GR00T → H2 als NEW_EMBODIMENT in GR00T (separate Datenpipeline, siehe `roadmap_groot.md`).

---

## 7. Offene Punkte — gegen aktuelle Doku zu verifizieren

Folgende Punkte erfordern Verifizierung mit Unitree/NVIDIA bei Projektstart:

1. **Exakte H2-URDF/MJCF-Definition**
   - Ist H2-MJCF/URDF in einem Unitree-Repo verfügbar (unitree_sim_isaaclab, unitree_mujoco)?
   - Falls nicht: Mesh-/Parameter-Export aus H2-Handbuch oder SDK.
   - Knöchel-Parallelmechanismus (PR/AB-Steuerung) — wie wird das in RL-Action-Raum gemappt?

2. **RL-Framework-Kompatibilität**
   - unitree_rl_lab: Welche IsaacLab-Version ist erforderlich? (aktuell 5.x empfohlen, 2026-06-30)
   - H2-Beispiel-Konfiguration in unitree_rl_lab vorhanden, oder muss von G1 abgeleitet werden?

3. **Hyperparameter-Richtlinien für H2-Masse**
   - G1-Reward-Gewichtungen für 35 kg → H2 für 70 kg? Skalierungsfaktoren?
   - Stabilisierungs-Gains (Kp, Kd) — welche Werte empfohlen Unitree?

4. **Trainingsdaten-Volumen für H2**
   - Historische G1-Trainings: Wie viele Steps bis zu 80%+ Erfolgsquote?
   - Für H2 (andere Dynamik) — 2× Steps erforderlich?

5. **Sim-to-Real-Transfer**
   - Domain-Randomization-Strategie empfohlen?
   - Häufigkeit echte Hardware-Tests vs. reines Sim-Training?

6. **Sensor-Drift und Kalibrierung im Feld**
   - IMU/Encoder-Drift auf realem H2 — wie wird Observability garantiert?
   - Fallback bei Sensor-Fehler (Watchdog)?

---

## 8. Nächste Schritte

### Phase 1: Vorbereitung (2–3 Wochen)

1. **RTX-GPU beschaffen** (mindestens RTX 4080; besser 4× H100 für Cluster).
2. **unitree_rl_lab klonen** → `training/` als Submodule oder Fork.
3. **H2-URDF/MJCF akquirieren** (Unitree-Repos durchsuchen oder von H2-Dokumentation herleiten).
4. **Unitree-Konfiguration für G1-Policy prüfen** → Gewichte-Ablage, Parameter-Layout.

### Phase 2: H2-Vorlage erstellen (2–4 Wochen)

1. **H2-MJCF/URDF validieren** im unitree_mujoco-Simulator.
2. **H2-RL-Config schreiben** (von G1-Template abgeleitet):
   - `training/h2_locomotion_config.yaml`
   - Gelenklisten, Reward-Funktionen, Normalisierungs-Parameter.
3. **Dummy-Policy-Inferenz testen** gegen unitree_mujoco.

### Phase 3: Training (variabel, Wochen–Monate)

1. **IsaacLab-Setup** auf Trainings-GPU.
2. **Trainingslauf starten** mit H2-Config.
3. **Progress-Logs monitoren** (Reward-Kurven, Stabilität-Metriken).
4. **Iterative Hyperparameter-Tunung** bei schlechtem Konvergieren.

### Phase 4: Validierung & Deployment (2–4 Wochen)

1. **Validierungs-Szenarien** im Twin erstellen (Kurvenfahrten, Hindernis-Navigation).
2. **Policy als ONNX exportieren** + TensorRT-Optimization.
3. **Real-World-Tests auf H2 EDU** (unter Aufsicht, Debug-Modus).
4. **Fallback-Logik** implementieren (bei Fehler → Teach-Replay).

---

## Referenzen

- **Unitree RL-Frameworks:**
  - `unitree_rl_lab` (GitHub, IsaacLab-Basis, empfohlen)
  - `unitree_rl_gym` (Isaac Gym, älter)
  - `unitree_rl_mjlab` (MuJoCo, CPU-Option)
  - G1-Policy-Checkpoints: Repository-Docs oder Unitree-Download

- **H2-Hardware / Kinematics:**
  - `docs/sdk_reference.md` (H2-Gelenk-Struktur, 29 DoF)
  - Unitree H2 EDU Handbuch (Gain-Empfehlungen, Motor-Spezifikationen)

- **Unsere Architektur:**
  - `docs/roadmap_groot.md` (Manipulation via GR00T; getrennte Policy)
  - `docs/dev_environment.md` (Stufe B/C: Echte Hardware, GPU-Setup)
  - `config/robot.sim_mujoco.yaml`, `training/h2_locomotion_deploy.yaml` (Konfiguration)

---

**Gültig ab:** 2026-07-06  
**Nächste Überprüfung:** Nach Beschaffung RTX-GPU und Prüfung gegen unitree_rl_lab aktueller Docs
