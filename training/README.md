# H2 laufen lernen — mit G1 als Vorlage

Dieser Ordner enthält das **Trainings-Gerüst** (Config + Mapping-Doku) für
eine eigene H2-Lauf-Policy, abgeleitet von Unitree G1 (`unitree_rl_gym`). Er
liegt bewusst **außerhalb** von `src/h2_loader/` — wie `groot/` (ADR-0007) ist
er nicht Teil des installierbaren Pakets und nicht Teil der Testsuite, weil er
sich auf Trainings-Frameworks/-Rigs bezieht, die hier nicht installiert sind.

**GPU-frei hier:** Dieser Ordner selbst enthält nur Config/Doku — kein
Training, kein Code, der eine GPU braucht. Das eigentliche Training läuft auf
einem separaten Linux+RTX-Rig (siehe Schritt 2).

## Dateien

- **`h2_locomotion_deploy.yaml`** — H2-Deploy-Config im Format von
  `unitree_rl_gym/deploy/deploy_mujoco/configs/g1.yaml`, mit G1-Startwerten
  (kps/kds/default_angles/Skalierungen) für die 12 Bein-DoF.
- **`h2_joint_map.md`** — Gelenk-Mapping H2 ↔ G1 (Aktionsindex ↔ Gelenkname),
  inkl. der Knöchel-Reihenfolge-Falle (H2 ≠ G1) und Arm-/Taillen-Übereinstimmung
  mit `g1_29dof`.

## Warum G1 als Vorlage taugt

G1 (`g1_29dof`) und H2 haben laut Gelenklisten aus den offiziellen Unitree-
Repos **identische Gelenknamen**: Arme 7/Seite (`shoulder_pitch/roll/yaw`,
`elbow`, `wrist_roll/pitch/yaw`), Taille 3 (`waist_yaw/roll/pitch`), Beine 12
(6/Bein mit 2-DoF-Knöchel `ankle_pitch`/`ankle_roll`). Die G1-Lauf-Policy aus
`unitree_rl_gym` steuert genau diese 12 Bein-Gelenke (`num_actions: 12`,
`num_obs: 47`). Das macht G1 zur naheliegendsten Trainings-Vorlage — siehe
`h2_joint_map.md` für die Details (inkl. einer Abweichung bei der
Knöchel-Reihenfolge).

**Was NICHT übertragbar ist:** Gains, Rewards, Default-Pose und erst recht die
trainierten Gewichte selbst. G1 ist ca. 1,3 m/35 kg, der H2 ca. 1,8 m/70 kg —
deutlich schwerer und größer. Eine eigene Trainingsrunde mit H2-URDF/MJCF ist
unumgänglich.

Kontext: ADR-0004 (`docs/adr/0004-h2-mobil-locomotion-layer.md`) hält fest,
dass `unitree_rl_gym` den H2 **nicht** offiziell unterstützt (nur
Go2/G1/H1/H1_2) und dass der bordeigene Onboard-Lauf-/Balance-Regler (PC1) der
heutige Standard-Weg ist. Eigenes RL-Training ist damit **Fallback**, falls
kein brauchbarer Onboard-Geh-Modus verfügbar ist — dieser Ordner bereitet
genau diesen Fallback vor.

## Framework-Wahl

| Framework | Sim | GPU nötig | Eignung |
|---|---|---|---|
| **`unitree_rl_lab`** (empfohlen) | Isaac Lab | Ja (RTX, Training) | Neuere Unitree-Referenz, u. a. `g1_29dof` Velocity-Policy als ONNX — nächstliegende Vorlage für ein H2-Äquivalent |
| **`unitree_rl_gym`** | Isaac Gym | Ja (RTX, Training) | Ältere, gut dokumentierte Referenz (dieses Gerüst ist von hier abgeleitet: `g1.yaml`, `g1_12dof.urdf`) |
| **`unitree_rl_mjlab`** | MuJoCo | Ja, aber genügsamer | GPU-ärmere Alternative, falls Isaac Lab/Isaac Gym auf dem Rig nicht laufen |

Alle drei folgen demselben Grundmuster: Env/Robot-Config (Gelenke, Gains,
Rewards) → Training auf GPU → Policy-Export (`.pt`/`.onnx`) → Deploy-Skript
mit CPU-Inferenz gegen MuJoCo oder echte Hardware.

## Schritt für Schritt

1. **H2 als Robot anlegen.** MJCF/URDF aus `unitree_mujoco`
   (`unitree_robots/h2/h2_mujoco.xml`, `scene.xml`) bzw. dem H2-URDF in das
   gewählte Framework einhängen. Gelenkliste, Gains-Startwerte und Rewards vom
   G1-Task (`g1.yaml`, G1-Rough-/Velocity-Config) als Ausgangspunkt kopieren —
   Gelenkreihenfolge dabei **immer** gegen die tatsächliche H2-MJCF prüfen
   (siehe `h2_joint_map.md`, Knöchel-Falle).
2. **Training auf RTX-GPU.** Isaac Lab/Isaac Gym brauchen eine echte
   Consumer-/Datacenter-RTX-GPU (Ray-Tracing-Kerne, ausreichend VRAM für
   parallele Envs). Die im Projekt vorhandene M4000 reicht dafür **nicht**
   (kein RTX, zu wenig VRAM für IsaacLab/Isaac Sim) — analog zur GR00T-Lage in
   `docs/groot_setup.md`. Training läuft auf einem separaten Linux+RTX-Rig,
   nicht auf dem H2 selbst und nicht auf dem Windows-Entwicklungsrechner.
3. **Policy exportieren.** Trainiertes Modell als `.pt` (TorchScript, wie
   `unitree_rl_gym`) oder `.onnx` (wie `unitree_rl_lab`) exportieren.
4. **Deploy im MuJoCo-Twin.** `deploy_mujoco.py` (aus dem gewählten Framework)
   mit `h2_locomotion_deploy.yaml` gegen `unitree_robots/h2/scene.xml` starten
   — CPU-Inferenz, kein Training nötig. Ergänzt den bestehenden Digital Twin
   aus `config/robot.sim_mujoco.yaml` (dort läuft der reale DDS-Stack gegen
   `unitree_mujoco`; die Lauf-Policy würde als zusätzlicher, separater Prozess
   `rt/lowcmd`/`rt/lowstate` bedienen — Details zur DDS-Kopplung sind hier noch
   nicht ausgearbeitet und wären ein eigener Folgeschritt).
5. **Sim-to-Real.** Erst nach erfolgreichem Twin-Test auf dem echten H2
   testen — mit denselben Sicherheitsauflagen wie in
   `docs/safety_concept.md` beschrieben (Notaus, Bereichsüberwachung; ein
   laufender Roboter ist eine andere Risikoklasse als ein stehender
   Manipulator).

## Ehrlicher Aufwands-Hinweis

- Gains, Rewards und `default_angles` in `h2_locomotion_deploy.yaml` sind
  **G1-Startwerte**, keine für H2 eingemessenen Werte — sie werden erst durch
  ein eigenes Training (Schritt 1–2) durch H2-taugliche Werte ersetzt.
  Gewichte/Checkpoints sind zwischen G1 und H2 **nicht übertragbar**
  (unterschiedliche Masse/Größe/Trägheit, siehe `h2_joint_map.md` Abschnitt 3).
- Training ist **GPU-pflichtig** (RTX-Rig, kein Ausweg über CPU-only oder die
  vorhandene M4000).
- Dieses Gerüst ersetzt **nicht** den Onboard-Lauf-/Balance-Regler
  (`OnboardLocomotion`, ADR-0004) als heutigen Standardweg — es bereitet den
  in ADR-0004 genannten Fallback vor, falls der Onboard-Geh-Modus nicht
  ausreicht.

## Weiterführende Dokumente

- `docs/locomotion_training.md` — Strategie-/Plan-Dokument (G1 als
  universelle Vorlage, Framework-Entscheidung, Pipeline, GR00T-Abgrenzung).
- `groot/` — GR00T-Vorbereitungsartefakte (ADR-0007); GR00T ist für
  **Manipulation** zuständig, nicht für Locomotion — beide Policies laufen
  am Ende nebeneinander (Laufen klassisch/RL, Greifen gelernt/GR00T).
- `config/robot.sim_mujoco.yaml` — bestehender Digital-Twin-Aufbau
  (unitree_mujoco, gleiche DDS-Schnittstelle wie real).
- `docs/adr/0004-h2-mobil-locomotion-layer.md` — Entscheidung
  `LocomotionInterface` + Onboard-Backend als Standard, RL-Training als
  Fallback.
