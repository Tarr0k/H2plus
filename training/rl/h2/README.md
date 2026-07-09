# H2-MJX-Trainingsumgebung

Aus der Playground-G1-Vorlage (`training/rl/_g1_reference/`) fuer den Unitree H2
adaptiertes Joystick-Locomotion-Env. Läuft NICHT in der `mujoco_playground`-
Registry (H2 ist kein Erstanbieter-Env) -- Instanziierung erfolgt direkt.

## Dateien

| Datei | Zweck |
|---|---|
| `h2_constants.py` | Aktuator-Reihenfolge, Site-/Body-/Sensor-Namen, Index-Gruppen fuer Reward-Terme |
| `base.py` | `H2Env`: Modell laden, Aktuator->qpos/qvel-Adress-Mapping, Sensor-Zugriffe |
| `joystick.py` | `H2JoystickFlatTerrain`: Reward/Beobachtung/Reset/Step (Kern der Env) |
| `randomize.py` | Domain-Randomization (Reibung, Masse, Armatur/Daempfung) |
| `build_h2_mjx_model.py` | Baut aus der echten H2-MJCF das MJX-taugliche Modell (einmalig, auf ematalos) |
| `make_hfields.py` | Erzeugt die Hoehenfeld-PNGs (`hfield_rough.png`/`hfield_stairs.png`) fuer die Terrain-Varianten, siehe unten |
| `xmls/` | Wird von `build_h2_mjx_model.py` erzeugt (nicht Teil des Repos vor dem ersten Build) |

## 1) Modell bauen (einmalig, auf ematalos)

```sh
~/mjxenv/bin/python ~/H2plus/training/rl/h2/build_h2_mjx_model.py \
    ~/unitree_mujoco/unitree_robots/h2/scene.xml
```

Erzeugt unter `training/rl/h2/xmls/`:
- `h2_mjx_feetonly.xml` (MJX-taugliches Modell: Mesh-/Zylinder-Kollision aus,
  Fuss-Boxen als `left_foot`/`right_foot`, IMU-Sites auf `imu_in_pelvis`/
  `imu_in_torso` umbenannt, kompletter G1-Sensor-Block ergaenzt, `<position>`-
  Aktuatoren). Das im Quellmodell bereits vorhandene Boden-Geom `floor` wird
  HIER entfernt (siehe `extract_and_remove_floor`) und stattdessen pro
  Terrain-Szene neu angelegt (siehe naechster Punkt) -- fuer flat_terrain
  1:1 rekonstruiert (keine Verhaltensaenderung), fuer rough/stairs durch ein
  Hoehenfeld ersetzt. So teilen sich alle drei Szenen denselben Roboter-Include.
- `scene_mjx_feetonly_flat_terrain.xml` / `scene_mjx_feetonly_rough_terrain.xml`
  / `scene_mjx_feetonly_stairs.xml` (Kosmetik + Boden-Block je Terrain, siehe
  `write_scene_xml`; identischer `home`-Keyframe in allen drei Dateien, per
  Vorwaerts-Kinematik berechnet -- terrain-unabhaengig, kein geschaetzter Wert).
  rough/stairs brauchen zusaetzlich `xmls/assets/hfield_rough.png` bzw.
  `hfield_stairs.png` (siehe Abschnitt "Terrain-Varianten" unten) sowie eine
  manuell kopierte `xmls/assets/rocky_texture.png`.
- `sensor.xml` (Kontakt-"found"-Sensoren)

Das Skript bricht mit Klartext-Fehler (+ Liste vorhandener Namen) ab, falls ein
erwarteter Aktuator/Site/Body nicht existiert -- siehe "Zu verifizieren" unten.

**Smoke-Test danach:**
```sh
~/mjxenv/bin/python -c "
import mujoco
m = mujoco.MjModel.from_xml_path('training/rl/h2/xmls/scene_mjx_feetonly_flat_terrain.xml')
print(m.nq, m.nv, m.nu, m.nkey)
"
```
Erwartung: `38 37 31 1`.

Empfehlenswert: das Modell einmal im Viewer oeffnen und den `home`-Keyframe
anschauen (`mujoco.viewer.launch(m, d)` nach `mujoco.mj_resetDataKeyframe`),
um die berechnete Becken-Hoehe/Stehpose visuell zu pruefen.

## Terrain-Varianten (rough_terrain / stairs)

Analog G1 (`registry`-Eintraege `G1JoystickFlatTerrain`/`G1JoystickRoughTerrain`,
hier stattdessen ueber den `task`-Parameter von `H2JoystickFlatTerrain`
gesteuert, siehe `h2_constants.task_to_xml`). BLIND (keine Hoehenkarten-
Beobachtung) -- reine Boden-Variation, keine Env-Logik-Aenderung; eine echte
Hoehenkarten-Wahrnehmung waere ein spaeterer Ausbauschritt (siehe
`joystick.py`-Modul-Docstring).

```sh
# 1) Hoehenfeld-PNGs erzeugen (nur numpy+Pillow, kein mujoco noetig):
~/mjxenv/bin/python ~/H2plus/training/rl/h2/make_hfields.py
# 2) Rocky-Textur MANUELL von der G1-Referenz kopieren (liegt im installierten
#    mujoco_playground-Paket, nicht im Repo):
cp <mujoco_playground-Installationspfad>/_src/locomotion/g1/xmls/assets/rocky_texture.png \
   ~/H2plus/training/rl/h2/xmls/assets/rocky_texture.png
# 3) Modell bauen (falls noch nicht geschehen, siehe Schritt 1 oben) -- schreibt
#    dabei automatisch alle drei Szenen (flat/rough/stairs).
# 4) Trainieren:
python train_playground.py --env H2JoystickFlatTerrain --task rough_terrain --smoke
python train_playground.py --env H2JoystickFlatTerrain --task stairs --smoke
```

**Wichtiger, noch UNVERIFIZIERTER Punkt** (siehe `make_hfields.py`-Docstring):
ob Bild-Zeile/-Spalte 0 in MuJoCo tatsaechlich auf die von `make_hfields.py`
angenommene Weltkoordinate faellt (fuer `stairs` wichtig, damit der Roboter
VOR der ersten Stufe spawnt, nicht mitten auf/hinter der Treppe) -- unbedingt
im Viewer gegenpruefen, ggf. `np.flipud`/`np.fliplr` in `make_stairs()` ergaenzen.
Ausserdem treibt die Env den Roboter NICHT gezielt auf die Treppe zu (zufaellige
Spawn-Rotation + zufaellige Kommandos wie bei flat_terrain) -- `stairs` ist
aktuell eher ein "manchmal wird die Treppe erreicht"-Robustheitsszenario als
echtes gerichtetes Treppensteigen-Training; fuer Letzteres braeuchte es
zusaetzlich eine Zielpunkt-/Waypoint-Konditionierung (nicht Teil dieser Aenderung).

## 2) Env direkt instanziieren (ohne Registry)

```python
from h2 import H2JoystickFlatTerrain, default_config

cfg = default_config()
cfg.impl = "jax"  # auf der M4000 zwingend (warp crasht, siehe train_playground.py)
env = H2JoystickFlatTerrain(config=cfg)
```

(`training/rl/` muss auf `sys.path` sein, damit `import h2` funktioniert --
`build_h2_mjx_model.py` und `train_playground.py` machen das bereits selbst.)

## 3) Training starten

`train_playground.py` wurde um einen Sonderfall fuer `H2JoystickFlatTerrain`
erweitert (`build_env`, `build_ppo_config`, Domain-Randomizer-Auswahl in
`main()`) -- alles andere (Checkpointing, Resume, CLI, `--smoke`) ist
unveraendert nutzbar:

```sh
python train_playground.py --env H2JoystickFlatTerrain --smoke   # Rauchtest
python train_playground.py --env H2JoystickFlatTerrain --num-envs 512 \
    --out-dir ~/h2_rl_runs/h2_v1
```

PPO-Hyperparameter werden dabei 1:1 von `G1JoystickFlatTerrain` uebernommen
(kein eigener H2-Registry-Eintrag vorhanden, keine erfundenen Zahlen).

## Wichtige Design-Entscheidung: Aktuator- vs. qpos-Reihenfolge

**Verifiziert** (`training/deploy/deploy_h2_g1policy.py`, Kommentar ab Zeile 11):
die qpos-Gelenkreihenfolge im H2-Modell ist *(Beine, Taille, Kopf, Arme)*,
die Aktuator-/`ctrl`-Reihenfolge ist *(Beine, Taille, Arme, Kopf)*. Bei G1
fallen beide zufaellig zusammen (die gesamte G1-Vorlage verlaesst sich darauf
und nutzt `qpos[7:]`/`qvel[6:]`-Slices) -- bei H2 NICHT.

Deshalb adressiert dieser Code **jedes** Gelenk ausschliesslich ueber seinen
**Aktuator-Namen** (`h2_constants.ACTUATOR_ORDER`), nie per Slice:
`base.py` baut bei Env-Konstruktion `self._qpos_adr`/`self._qvel_adr`
(`actuator_trnid` -> `jnt_qposadr`/`jnt_dofadr`), und `joystick.py` verwendet
ausschliesslich `self.get_actuator_qpos/-qvel/-qacc(data)` statt
`data.qpos[7:]` etc. Wer an diesem Code weiterarbeitet: **niemals** ein neues
`[7:]`/`[6:]`-Slice einfuehren, ohne das explizit zu pruefen.

## Vereinfachungen gegenueber G1 (kein Vorbild-Datenmaterial vorhanden)

- **Keine Hand-Oberschenkel-/Fuss-Schienbein-Kollision**: G1 hat dafuer
  eigene Kapsel-Kollisionsgeome; fuer H2 sind deren Masse/Position nicht
  verifiziert. Nur die Fuss-Boxen (`left_foot`/`right_foot`) kollidieren
  (gegen Boden und gegeneinander). `_cost_collision` sowie die Schienbein-
  Terminierungsbedingung aus der G1-Vorlage entfallen.
- **`RESTRICTED_JOINT_RANGE`**: G1 hat literal aus dem Datenblatt uebernommene
  Sicherheitsgrenzen. Fuer H2 gibt es die nicht -- `h2_constants.restricted_joint_range()`
  leitet sie stattdessen zur Laufzeit als 90%-Fenster der ECHTEN (aus dem
  Modell gelesenen) `jnt_range` ab. Bei Bedarf durch echte Datenblattwerte
  ersetzen.
- **kp/damping/armature**: 1:1 aus der G1-Vorlage uebernommen, aber NUR als
  Fallback dort, wo das Original-H2-Gelenk keinen nennenswerten Wert hat
  (siehe `build_h2_mjx_model.py::rebuild_actuators`). Kopf-Gelenke haben kein
  G1-Vorbild und sind an die leichteste G1-Klasse (Handgelenk) angelehnt --
  klare Annahme, zum Nachjustieren markiert.
- **`<option>` (Solver/Timestep)**: bewusst NICHT angefasst -- das Team hat
  mit den Original-H2-Werten bereits ~12k Steps/s in MJX erreicht.

## G1-Imitation (optionaler Reward-Term, standardmaessig AUS)

`joystick.py` kennt einen zusaetzlichen Reward-Term `imitation`
(`reward_config.scales.imitation`, Default `0.0`), der die 12 Bein-Gelenkwinkel
weich in Richtung einer phasenindizierten G1-Gangreferenz zieht -- gedacht als
Stil-Fuehrung, die H2 aus dem bisherigen Plateau (Episodenlaenge ~65 bei reinem
Task-/Balance-Reward) herausholen soll, statt den Gang komplett "aus dem Nichts"
zu suchen. **Kein exaktes Nachahmen**: reines Kopieren von G1s Gelenkwinkeln haelt
den gut doppelt so schweren H2 NICHT aufrecht (verifiziert in
`training/deploy/deploy_h2_g1policy.py`: Sturz nach ~1,5 s) -- der Term ist additiv
neben dem bestehenden Tracking-/Balance-Reward, sein Gewicht ist bewusst tunebar.

### Ablauf

1. **Referenzgang aufzeichnen** (auf ematalos, braucht kurz die GPU + die
   trainierte G1-Policy unter `~/h2_rl_runs/g1_full/best`):
   ```sh
   XLA_PYTHON_CLIENT_ALLOCATOR=platform python training/rl/h2/extract_g1_reference.py \
       --ckpt ~/h2_rl_runs/g1_full/best --steps 4000 --vx 0.5
   ```
   Rollt die G1-Policy mit FESTEM Kommando (`vx=0.5, vy=0, yaw=0` per Default) aus,
   bin(n)t die 12 Bein-Gelenkwinkel nach Gangphase (`state.info["phase"]`, 32 Bins
   per Default), glaettet zirkular und retargetet auf H2-Gelenkreihenfolge
   (Knoechel-Swap, siehe oben). Schreibt `training/rl/h2/assets/g1_gait_reference.npy`
   + `.json`-Metadaten (Bins, Kommando, Quelle, Stichprobenzahl je Bin).

2. **Imitations-Gewicht aktivieren** (Training mit `--env H2JoystickFlatTerrain`):
   ```sh
   python train_playground.py --env H2JoystickFlatTerrain --imitation-weight 1.0 \
       --out-dir ~/h2_rl_runs/h2_imitation
   ```
   Setzt intern `reward_config.scales.imitation` per `config_overrides` (siehe
   `train_playground.py::build_env`). Ohne `--imitation-weight` bleibt der Term bei
   `0.0` (Default) -- bestehende flat/rough/stairs-Laeufe sind unveraendert.
   `--imitation-weight` ist nur fuer `--env H2JoystickFlatTerrain` wirksam (G1s
   Reward-Config kennt keinen `imitation`-Skalenwert).

Fehlt `assets/g1_gait_reference.npy` (Schritt 1 noch nicht gelaufen), bleibt der
Term inaktiv (klare Warnung beim Env-Start), auch wenn ein Gewicht > 0 gesetzt ist
-- das Training laeuft trotzdem normal weiter.

## Zu verifizieren, bevor dem Ergebnis vertraut wird

1. **Aktuator-Namen fuer Taille/Arme/Kopf** (`h2_constants._WAIST_/_ARM_/
   _HEAD_SUFFIXES`): nur die 12 Bein-Namen sind ueber `deploy_h2_g1policy.py`
   verifiziert, der Rest ist nach demselben Schema extrapoliert.
   `build_h2_mjx_model.py` bricht ab und listet die tatsaechlich vorhandenen
   Aktuatoren, falls ein Name falsch geraten ist -- Fehlermeldung genau lesen
   und `h2_constants.py` entsprechend korrigieren.
2. **Fuss-Sohlen-Box**: Skript erwartet genau EIN Box-Geom direkt unter
   `<seite>_ankle_pitch_link` (im Original UNBENANNT, Team-Notiz) -- Bricht
   mit Klartext-Fehler ab, falls nicht so.
3. **IMU-Sites** `imu` (Becken) / `secondary_imu` (Torso): Skript prueft deren
   Existenz und benennt sie auf `imu_in_pelvis`/`imu_in_torso` um (inklusive
   aller Referenzen, auch der 101 bereits vorhandenen H2-Sensoren -- siehe
   `rename_site_everywhere`). Bricht ab, falls die Original-Namen fehlen.
4. **Boden-Geom `floor`**: existiert laut Team-Notiz bereits (type plane,
   contype=1). Skript prueft dessen Existenz, LOEST es dann aus dem Roboter-
   XML heraus (`extract_and_remove_floor`) und legt es JE TERRAIN-SZENE neu an
   (fuer flat_terrain unveraendert rekonstruiert, siehe "Terrain-Varianten"
   oben) -- KEINE zweite Bodenebene im selben Include (das gaebe einen
   "repeated name"-Fehler beim Kompilieren).
5. **Sensor-Frame-Suffixe** (`upvector_pelvis`/`upvector_torso` etc.): werden
   vom Build-Skript selbst angelegt (Site `imu_in_pelvis` -> Suffix `pelvis`,
   Site `imu_in_torso` -> Suffix `torso`) -- kein externes Verifikationsrisiko,
   aber gut zu wissen, falls im Viewer nach Sensor-Namen gesucht wird.
6. **Becken-Hoehe des `home`-Keyframes**: wird beim Bauen geloggt und per
   Vorwaerts-Kinematik (nicht geschaetzt) bestimmt -- trotzdem kurz im Viewer
   gegenpruefen, ob die Pose aufrecht/plausibel aussieht.
7. **`actuator_ctrlrange`/`forcerange`**: `rebuild_actuators` uebernimmt
   `forcerange` vom Original-`<motor>`-Aktuator, falls dort `forcelimited`
   gesetzt ist. Falls das Original KEINE Kraftgrenzen hat, bleiben die neuen
   `<position>`-Aktuatoren unbegrenzt (`inheritrange="1"` beschraenkt nur die
   Soll-Position, nicht die Kraft) -- bei Bedarf reale Motor-Drehmomentgrenzen
   nachtragen.
8. **Terrain-Varianten** (siehe Abschnitt oben, NEU): `make_hfields.py` wurde
   lokal (nur numpy/Pillow, ohne mujoco) gegen die reine Bild-Erzeugungslogik
   getestet (Graustufen-Profil der Treppe stimmt: 6 Stufen sichtbar, Werte
   0/42/85/127/170/212/255 symmetrisch rauf/runter) -- NICHT getestet ist die
   MuJoCo-seitige Zeile/Spalte-zu-Weltkoordinate-Zuordnung des `<hfield>` (ob
   der Roboter beim Spawn tatsaechlich VOR der ersten Stufe steht). Ausserdem
   `naconmax`/`njmax` in `joystick.py::default_config()` wurden fuer flat_terrain
   dimensioniert (3 explizite Fuss-Pairs) -- ob Box-gegen-Hoehenfeld-Kollision
   (rough/stairs) mehr Kontaktpunkte pro Pair erzeugt und die Limits erhoeht
   werden muessen, ist auf ematalos gegenzupruefen (Compile-Fehler/Warnung bei
   Kontakt-Ueberlauf waeren das Signal).
