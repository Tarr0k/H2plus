# H2 ↔ G1 Gelenk-Mapping (Lauf-Policy)

> Quellen: `unitree_rl_gym` (`resources/robots/g1_description/g1_12dof.urdf`,
> `deploy/deploy_mujoco/configs/g1.yaml`) und `unitree_mujoco`
> (`unitree_robots/h2/h2_mujoco.xml`), jeweils per `gh api` gegen die
> tatsächlichen Repo-Inhalte geprüft (Stand 2026-07-06). Siehe auch
> `training/h2_locomotion_deploy.yaml`, `training/README.md`.

## 1. Die 12 Bein-Gelenke (von der Lauf-Policy gesteuert)

Die G1-Lauf-Policy (`unitree_rl_gym`, `num_actions: 12`) steuert ausschließlich
die 12 Bein-Gelenke. Der H2 hat **dieselbe Bein-Kinematik** (6 DoF/Bein,
2-DoF-Knöchel) und **dieselben Gelenknamen**.

| Aktionsindex | G1-Gelenk (g1_12dof.urdf) | H2-Gelenk (h2_mujoco.xml) |
|---|---|---|
| 0 | `left_hip_pitch_joint` | `left_hip_pitch_joint` |
| 1 | `left_hip_roll_joint` | `left_hip_roll_joint` |
| 2 | `left_hip_yaw_joint` | `left_hip_yaw_joint` |
| 3 | `left_knee_joint` | `left_knee_joint` |
| 4 | `left_ankle_pitch_joint` | **`left_ankle_roll_joint`** |
| 5 | `left_ankle_roll_joint` | **`left_ankle_pitch_joint`** |
| 6 | `right_hip_pitch_joint` | `right_hip_pitch_joint` |
| 7 | `right_hip_roll_joint` | `right_hip_roll_joint` |
| 8 | `right_hip_yaw_joint` | `right_hip_yaw_joint` |
| 9 | `right_knee_joint` | `right_knee_joint` |
| 10 | `right_ankle_pitch_joint` | **`right_ankle_roll_joint`** |
| 11 | `right_ankle_roll_joint` | **`right_ankle_pitch_joint`** |

Die Gelenknamen sind identisch — nur die **Reihenfolge im Aktionsvektor**
unterscheidet sich am Knöchel (fett markiert).

### Achtung: Knöchel-Reihenfolge

- **G1** deklariert je Bein `hip_pitch → hip_roll → hip_yaw → knee →
  ankle_pitch → ankle_roll` (URDF-Gelenkreihenfolge = MJCF-Motorreihenfolge =
  `qpos`-Reihenfolge in `deploy_mujoco.py`).
- **H2** deklariert je Bein `hip_pitch → hip_roll → hip_yaw → knee →
  ankle_roll → ankle_pitch` — Knöchel **vertauscht** gegenüber G1 (verifiziert
  sowohl in der `<joint>`-Verschachtelung als auch in der `<actuator>`-Liste
  von `h2_mujoco.xml`; beide sind bei H2 konsistent zueinander).
- **Konsequenz:** Wer G1-Arrays (`default_angles`, trainierte Policy-Gewichte
  o.ä.) unreflektiert 1:1 auf den H2-Aktionsvektor kopiert, vertauscht
  `ankle_roll`- und `ankle_pitch`-Werte. In `h2_locomotion_deploy.yaml` ist das
  bereits korrigiert (`default_angles` umsortiert). Bei kps/kds wirkt sich der
  Tausch nicht aus, weil G1 für beide Knöchel-DoF denselben Gain-Wert nutzt
  (40 / 2) — das ist bei H2 (andere Aktuatoren, siehe `ctrlrange` unten) nicht
  zwangsläufig so und beim H2-Tuning zu prüfen.
- Zum Vergleich die `ctrlrange` (Motor-Drehmomentgrenzen) aus
  `h2_mujoco.xml`: `ankle_roll` ±19 Nm, `ankle_pitch` ±66,88 Nm — der
  Pitch-Aktuator ist am H2 deutlich stärker ausgelegt als der Roll-Aktuator
  (plausibel: Pitch trägt die Abstoßkraft beim Gehen).
- **Bei jeder neuen H2-Trainings-Config (Rewards, Joint-Limits, Export-ONNX)
  erneut gegen die tatsächliche H2-URDF/MJCF-Gelenkreihenfolge prüfen** — nicht
  blind von G1 übernehmen.

## 2. Arme (14) und Taille (3) — dieselben Gelenknamen wie g1_29dof

H2 und `g1_29dof` (die 29-DoF-Variante von G1, nicht die 12-DoF-Lauf-Variante)
verwenden für Arme und Taille **identische Gelenknamen**:

- Taille (3): `waist_yaw_joint`, `waist_roll_joint`, `waist_pitch_joint`
- Arm je Seite (7): `shoulder_pitch_joint`, `shoulder_roll_joint`,
  `shoulder_yaw_joint`, `elbow_joint`, `wrist_roll_joint`, `wrist_pitch_joint`,
  `wrist_yaw_joint` (Präfix `left_`/`right_`)

→ **Mapping ist trivial** (1:1 Namensgleichheit, keine Umsortierung nötig).

Diese 17 Gelenke werden von der hier vorbereiteten **Lauf-Policy nicht
gesteuert** (`num_actions: 12`, nur Beine). Arm-/Taillen-Bewegung läuft am H2
weiterhin über den bestehenden Teach-in-/GR00T-Pfad (`groot/`,
`docs/roadmap_groot.md`) bzw. wird für eine Ganzkörper-Policy separat
behandelt — das ist hier **nicht** Umfang.

Der H2 hat zusätzlich 2 Kopf-Gelenke (`head_pitch_joint`, `head_yaw_joint`),
die laut `h2_mujoco.xml` **keinen** `<motor>`-Eintrag haben (passiv/nicht
aktuiert) — kein Gegenstück in dieser Lauf-Policy nötig.

## 3. H2 vs. G1 — Größen-/Massenwarnung

| | G1 | H2 |
|---|---|---|
| Größe | ca. 1,3 m | ca. 1,8 m |
| Gewicht | ca. 35 kg | ca. 70 kg |

Gleiche Gelenknamen/-topologie bedeuten **nicht**, dass G1-Gains, -Rewards
oder gar eine G1-trainierte Policy direkt auf dem H2 laufen. Masse, Trägheit,
Hebelarme und Aktuator-Drehmomentgrenzen unterscheiden sich deutlich (siehe
`ctrlrange`-Werte in `h2_mujoco.xml`, z. B. Hüfte ±360 Nm am H2). Die Werte in
`training/h2_locomotion_deploy.yaml` sind **Startwerte für ein eigenes
H2-Training**, keine einsatzbereite H2-Policy. Details: `training/README.md`.
