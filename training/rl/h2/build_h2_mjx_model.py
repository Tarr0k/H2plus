"""build_h2_mjx_model.py -- baut aus der echten H2-MJCF ein MJX-taugliches
"feetonly"-Modell + Szene (analog `_g1_reference/xmls/g1_mjx_feetonly.xml` +
`scene_mjx_feetonly_flat_terrain.xml`).

LAEUFT NUR AUF EMATALOS (braucht ein echtes `mujoco`-Package + das reale H2-
Modell). Wird NICHT von Claude ausgefuehrt -- nur geschrieben.

Aufruf (Beispiel, siehe README.md):
    python build_h2_mjx_model.py ~/unitree_mujoco/unitree_robots/h2/scene.xml

Was das Skript macht (in dieser Reihenfolge):
  1. Laedt die Quell-MJCF EINMAL komplett ueber `mujoco.MjModel.from_xml_path`
     (loest <include>, meshdir, Compiler-Defaults etc. korrekt auf -- das kann
     eine simple `xml.etree.ElementTree`-Parse allein NICHT, da <include> eine
     MuJoCo-Compiler-Eigenheit ist, kein Standard-XML-Feature).
  2. Prueft NAMENSBASIERT (mj_name2id), dass alle von den H2-Env-Klassen
     benoetigten Elemente existieren (31 Aktuatoren, IMU-Sites, Wurzel-Body,
     Fuss-Sohlen-Box je Seite) -- bricht mit Klartext-Fehler + Liste der
     TATSAECHLICH vorhandenen Namen ab, falls nicht (siehe `verify_and_introspect`).
  3. Schreibt eine "flache" Kopie der kompilierten XML (`mj_saveLastXML`, loest
     <include> endgueltig auf) und bearbeitet DIESE per `xml.etree.ElementTree`:
       - Mesh-/Zylinder-/Ellipsoid-Kollisionsgeome auf contype=conaffinity=0
         (MJX kann diese Formen nicht kollidieren, verifiziert:
         NotImplementedError). NUR Kollisions-relevant, Optik bleibt unberuehrt.
       - IMU-Sites "imu"/"secondary_imu" (Original-Namen, Team-Notiz) werden auf
         die G1-kompatiblen Namen "imu_in_pelvis"/"imu_in_torso" umbenannt --
         inklusive ALLER Referenzen (auch der 101 bereits vorhandenen H2-
         Sensoren), siehe `rename_site_everywhere`. So braucht keine Env-Klasse
         einen H2-Sonderfall fuer Site-Namen.
       - Fuss-Sohlen-Box je Seite (bereits im Modell vorhanden, aber UNBENANNT,
         siehe Team-Notiz) wird zu "left_foot"/"right_foot" umbenannt; je eine
         Site an derselben Position wird hinzugefuegt (H2 hat dafuer noch keine
         Sites).
       - <contact><pair>-Eintraege links/rechts-Fuss<->Boden (gegen das bereits
         vorhandene Boden-Geom "floor", siehe Team-Notiz) sowie links<->rechts
         (Selbstkollision) -- exakt das G1-Muster, das NICHT auf contype/
         conaffinity-Breitband-Filterung angewiesen ist, sondern Kontaktpaare
         explizit deklariert (robust unabhaengig vom Ausgangswert von
         contype/conaffinity).
       - Das Boden-Geom "floor" selbst wird HIER aus dem Roboter-XML entfernt
         (siehe `extract_and_remove_floor`) und stattdessen JE TERRAIN-SZENE
         (flat/rough/stairs) neu angelegt (siehe Schritt 4/`write_scene_xml`)
         -- fuer flat_terrain 1:1 aus den Original-Attributen rekonstruiert
         (keine Verhaltensaenderung), fuer rough/stairs durch ein Hoehenfeld
         ersetzt. Grund: alle drei Varianten sollen denselben Roboter-Include
         nutzen, brauchen aber unterschiedliche Boeden.
       - Kompletter <actuator>-Neuaufbau als <position>-Aktuatoren (das
         Quellmodell nutzt <motor>, siehe deploy_h2_g1policy.py, das `d.ctrl`
         manuell per PD-Regler befuellt -- fuer die MJX-Policy brauchen wir wie
         bei G1 native Positions-Regelung). kp/damping/armature je Gelenkklasse
         1:1 aus der G1-Vorlage uebernommen (NUR wenn das Original keinen
         nennenswerten Wert hat -- echte Herstellerangaben haben Vorrang).
         `forcerange` wird vom Original-<motor>-Aktuator uebernommen, falls
         vorhanden (reale Drehmoment-Grenzen, nicht erfunden).
       - Kompletter G1-Sensor-Block (upvector/local_linvel/accelerometer/gyro/
         global_linvel/global_angvel/forwardvector/orientation je "pelvis"+
         "torso"-Frame, plus Fuss-Kraft-/Geschwindigkeitssensoren) wird IN DEN
         BESTEHENDEN <sensor>-Block ERGAENZT -- die 101 bereits vorhandenen
         H2-Sensoren (Team-Notiz) bleiben unangetastet.
  4. Schreibt `sensor.xml` (Kontakt-"found"-Sensoren, analog G1) sowie DREI
     Szenen-Dateien (flat_terrain/rough_terrain/stairs, siehe `TERRAINS`),
     jede mit `<include>` von Robotermodell + `sensor.xml`, aber eigenem
     Boden-Block (siehe `write_scene_xml`/`_floor_block_xml`).
  5. Bestimmt die "home"-Keyframe-Werte NICHT durch Schaetzen, sondern per
     FORWARD-KINEMATIK (siehe `compute_home_qpos`): Beine auf die von der
     Team-Notiz vorgegebene Stehpose, danach wird das Becken exakt so hoch
     gesetzt, dass beide Fuss-Sohlen den Boden beruehren (+5 mm Clearance).
     Terrain-unabhaengig (der Boden spielt fuer diese Kinematik keine Rolle)
     -- DERSELBE Keyframe landet in allen drei Szenen-Dateien.
  6. Laedt flat_terrain zur Kontrolle noch einmal komplett (Smoke-Test:
     kompiliert es ueberhaupt?) und gibt nq/nv/nu/nkey aus -- verbindlich.
     rough_terrain/stairs werden ebenfalls geladen, aber nur BEST-EFFORT
     (Warnung statt Abbruch): ihnen fehlen direkt nach diesem Lauf i.d.R.
     noch die per `make_hfields.py` erzeugten Hoehenfeld-PNGs sowie die
     manuell zu kopierende `assets/rocky_texture.png` (siehe README.md).

WICHTIG -- vor dem ersten Training auf ematalos zu verifizieren (Skript bricht
bei 2./3. selbststaendig mit Klartext-Fehler ab, falls falsch geraten):
  - Aktuator-Namen fuer Taille/Arme/Kopf (Beine sind ueber
    `deploy_h2_g1policy.py` bereits verifiziert, siehe h2_constants.py).
  - Dass unter jedem "<seite>_ankle_pitch_link" GENAU ein Box-Geom (die Sohle)
    haengt.
  - Dass die Original-Sites "imu" und "secondary_imu" existieren (werden beim
    Bauen auf "imu_in_pelvis"/"imu_in_torso" umbenannt).
  - Dass ein Boden-Geom "floor" existiert (dessen Original-Attribute werden
    fuer flat_terrain wiederverwendet, siehe `extract_and_remove_floor`; fuer
    rough_terrain/stairs durch ein Hoehenfeld ersetzt).
Ausserdem NICHT automatisch geprueft, aber wichtig gegenzulesen:
  - Ob `<option>` (Timestep/Solver) der Quell-Datei sinnvoll ist -- dieses
    Skript FASST `<option>` BEWUSST NICHT AN (das Team hat mit den Original-
    Werten bereits ~12k Steps/s in MJX erreicht, siehe Team-Notiz).
  - Die berechnete Becken-Hoehe des "home"-Keyframes (wird beim Bauen
    ausgegeben) -- kurz im Viewer pruefen, ob die Pose plausibel aussieht.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional

import numpy as np

try:
  import mujoco
except ImportError as exc:  # pragma: no cover -- laeuft nur auf ematalos.
  raise SystemExit(
      "Dieses Skript braucht ein echtes mujoco-Package (siehe training/rl/README.md, "
      "~/mjxenv) und laeuft NUR auf ematalos, nicht auf dem Windows-Entwicklungsrechner."
  ) from exc

# Erlaubt den Aufruf sowohl als Modul (`python -m h2.build_h2_mjx_model`) als
# auch als eigenstaendiges Skript (`python build_h2_mjx_model.py ...`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import h2_constants as consts  # noqa: E402


# --- Gelenkklassen-Parameter (1:1 aus der G1-Vorlage, siehe -----------------
# _g1_reference/xmls/g1_mjx_feetonly.xml <default>-Block) -- NUR als Fallback,
# falls das Original-Gelenk keinen nennenswerten damping/armature-Wert hat.
# Kopf-Klassen (kein G1-Vorbild) sind an die leichteste G1-Klasse (Handgelenk)
# angelehnt -- klar als Annahme markiert, zum Nachjustieren gedacht.
JOINT_CLASS_PARAMS = {
    "hip_pitch":      dict(kp=75, damping=2.0, armature=0.01017752004),
    "hip_roll":       dict(kp=75, damping=2.0, armature=0.025101925),
    "hip_yaw":        dict(kp=75, damping=2.0, armature=0.01017752004),
    "knee":           dict(kp=75, damping=2.0, armature=0.025101925),
    "ankle_roll":     dict(kp=2,  damping=0.2, armature=0.00721945),
    "ankle_pitch":    dict(kp=20, damping=1.0, armature=0.00721945),
    "waist_yaw":      dict(kp=75, damping=2.0, armature=0.01017752004),
    "waist_roll":     dict(kp=75, damping=2.0, armature=0.00721945),
    "waist_pitch":    dict(kp=75, damping=2.0, armature=0.00721945),
    "shoulder_pitch": dict(kp=75, damping=2.0, armature=0.003609725),
    "shoulder_roll":  dict(kp=75, damping=2.0, armature=0.003609725),
    "shoulder_yaw":   dict(kp=75, damping=2.0, armature=0.003609725),
    "elbow":          dict(kp=75, damping=2.0, armature=0.003609725),
    "wrist_roll":     dict(kp=2,  damping=0.2, armature=0.003609725),
    "wrist_pitch":    dict(kp=2,  damping=0.2, armature=0.00425),
    "wrist_yaw":      dict(kp=2,  damping=0.2, armature=0.00425),
    # ANNAHME (kein G1-Vorbild): Kopfgelenke wie Handgelenke behandelt.
    "head_pitch":     dict(kp=2,  damping=0.2, armature=0.00425),
    "head_yaw":       dict(kp=2,  damping=0.2, armature=0.00425),
}
DEFAULT_FRICTIONLOSS = 0.1  # G1-Top-Level-Default, gilt fuer alle Gelenkklassen.

# Nominale Stehpose je Bein-Gelenkklasse (Team-Notiz, H2-Knoechelreihenfolge
# roll VOR pitch). Taille/Arme/Kopf bleiben in der Home-Pose auf 0.
LEG_HOME_POSE = {
    "hip_pitch": -0.3, "hip_roll": 0.0, "hip_yaw": 0.0,
    "knee": 0.6, "ankle_roll": 0.0, "ankle_pitch": -0.3,
}

MJX_UNSUPPORTED_TYPES = {"mesh", "cylinder", "ellipsoid"}

# Original-Site-Namen im Quellmodell (Team-Notiz). Werden beim Bauen auf die
# G1-kompatiblen Namen in h2_constants.py (PELVIS_IMU_SITE/TORSO_IMU_SITE)
# umbenannt -- siehe `rename_site_everywhere`.
SOURCE_PELVIS_IMU_SITE = "imu"
SOURCE_TORSO_IMU_SITE = "secondary_imu"

# --- Terrain-Varianten (flat/rough/stairs) ----------------------------------
# Das Boden-Geom "floor" steckt im H2-Quellmodell bereits IM Roboter-Teil
# (Team-Notiz). Damit rough_terrain/stairs einen ANDEREN Boden bekommen
# koennen, ohne den Roboter-Include zu verdoppeln, wird "floor" HIER aus dem
# Roboter-XML herausgeloest (siehe `extract_and_remove_floor`) und stattdessen
# JE SZENE neu angelegt (siehe `write_scene_xml`) -- exakt das G1-Muster, wo
# der Boden ebenfalls nie Teil von `g1_mjx_feetonly.xml` ist, sondern jeder
# `scene_mjx_feetonly_*.xml` einzeln (vgl. `_g1_reference/xmls/
# scene_mjx_feetonly_rough_terrain.xml`). Fuer "flat_terrain" ist das eine
# reine Verlagerung OHNE Verhaltensaenderung (die Original-Attribute werden
# 1:1 rekonstruiert).
TERRAINS = ("flat_terrain", "rough_terrain", "stairs")

# Hoehenfeld-Groessen als MuJoCo-<hfield>-`size`-Attribut ("radius_x radius_y
# elevation_z base_z", Meter). `elevation_z` ist die Hoehe, der Graustufe 255
# im PNG entspricht -- MUSS mit den `*_MAX_HEIGHT_M`-Konstanten in
# `make_hfields.py` uebereinstimmen (keine automatische Kopplung, siehe
# dortiger Modul-Docstring!). `radius_x`/`radius_y` (hier 10 10, wie G1)
# muessen ebenfalls mit `make_hfields.py::HFIELD_HALF_EXTENT_M` uebereinstimmen.
HFIELD_ROUGH_SIZE = "10 10 0.06 1.0"
HFIELD_STAIRS_SIZE = "10 10 0.90 1.0"


# --------------------------------------------------------------------------- #
# Schritt 1+2: Laden + Verifizieren (auf dem ORIGINAL, kompilierten Modell)
# --------------------------------------------------------------------------- #

def _name2id(model: "mujoco.MjModel", objtype, name: str) -> int:
  return mujoco.mj_name2id(model, objtype, name)


def verify_and_introspect(model: "mujoco.MjModel") -> Dict:
  """Prueft alle benoetigten Namen im ORIGINAL-Modell, sammelt Fakten (echte
  Gelenknamen je Aktuator, Fuss-Sohlen-Geometrie, Drehmomentgrenzen). Bricht
  mit Klartext-Fehler ab statt zu raten.
  """
  info: Dict = {}

  actuator_joint: Dict[str, str] = {}
  actuator_forcerange: Dict[str, Optional[np.ndarray]] = {}
  missing = []
  for act_name in consts.ACTUATOR_ORDER:
    aid = _name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, act_name)
    if aid < 0:
      missing.append(act_name)
      continue
    jid = model.actuator_trnid[aid, 0]
    actuator_joint[act_name] = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, jid)
    if bool(model.actuator_forcelimited[aid]):
      actuator_forcerange[act_name] = model.actuator_forcerange[aid].copy()
    else:
      actuator_forcerange[act_name] = None
  if missing:
    vorhanden = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)
    ]
    raise SystemExit(
        f"[FEHLER] {len(missing)} erwartete Aktuatoren fehlen im Quellmodell: {missing}\n"
        f"Tatsaechlich vorhandene Aktuatoren ({model.nu}): {vorhanden}\n"
        "Die Bein-Namen sind ueber training/deploy/deploy_h2_g1policy.py verifiziert; "
        "vermutlich weicht die Namenskonvention fuer Taille/Arme/Kopf davon ab -- "
        "h2_constants.py (_WAIST_/_ARM_/_HEAD_SUFFIXES) entsprechend anpassen."
    )
  info["actuator_joint"] = actuator_joint
  info["actuator_forcerange"] = actuator_forcerange

  # IMU-Sites tragen im Quellmodell noch ihre Original-Namen (Team-Notiz) --
  # `consts.PELVIS_IMU_SITE`/`TORSO_IMU_SITE` sind bereits die ZIEL-Namen nach
  # dem Umbenennen (siehe `rename_site_everywhere` in main()).
  for site in (SOURCE_PELVIS_IMU_SITE, SOURCE_TORSO_IMU_SITE):
    if _name2id(model, mujoco.mjtObj.mjOBJ_SITE, site) < 0:
      raise SystemExit(f"[FEHLER] erwartete IMU-Site '{site}' nicht im Quellmodell gefunden.")

  if _name2id(model, mujoco.mjtObj.mjOBJ_BODY, consts.ROOT_BODY) < 0:
    raise SystemExit(f"[FEHLER] erwarteter Wurzel-Body '{consts.ROOT_BODY}' nicht gefunden.")

  # Team-Notiz: Boden-Geom heisst im Original bereits "floor" -- wird
  # wiederverwendet (siehe write_scene_xml), deshalb hier nur verifizieren.
  if _name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor") < 0:
    raise SystemExit(
        "[FEHLER] erwartetes Boden-Geom 'floor' nicht im Quellmodell gefunden -- "
        "pruefen, ob die Quelldatei sich geaendert hat (siehe Team-Notiz)."
    )

  foot_geom: Dict[str, Dict] = {}
  for side in ("left", "right"):
    body_name = f"{side}_ankle_pitch_link"
    bid = _name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if bid < 0:
      raise SystemExit(f"[FEHLER] erwarteter Fuss-Body '{body_name}' nicht gefunden.")
    box_geoms = [
        g for g in range(model.ngeom)
        if model.geom_bodyid[g] == bid and model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX
    ]
    if len(box_geoms) != 1:
      geoms_hier = [
          mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g) or f"#{g}"
          for g in range(model.ngeom) if model.geom_bodyid[g] == bid
      ]
      raise SystemExit(
          f"[FEHLER] erwarte genau EIN Box-Geom (Sohle) in Body '{body_name}', "
          f"gefunden: {len(box_geoms)}. Geoms in diesem Body: {geoms_hier}"
      )
    gid = box_geoms[0]
    foot_geom[side] = {
        "body": body_name,
        "pos": model.geom_pos[gid].copy(),
    }
  info["foot_geom"] = foot_geom
  return info


# --------------------------------------------------------------------------- #
# Schritt 3: Abflachen + ElementTree-Bearbeitung
# --------------------------------------------------------------------------- #

def flatten_xml(source_xml: Path) -> Path:
  """Laesst MuJoCo <include>/Compiler-Defaults aufloesen und schreibt eine
  flache Kopie NEBEN der Quelldatei (relative Mesh-Pfade bleiben so beim Laden
  gueltig, bevor `absolutize_asset_paths` sie endgueltig auf absolute Pfade
  umstellt).
  """
  model = mujoco.MjModel.from_xml_path(str(source_xml))
  flat_path = source_xml.parent / f"_{source_xml.stem}_flat.xml"
  mujoco.mj_saveLastXML(str(flat_path), model)
  return flat_path


def absolutize_asset_paths(root: ET.Element, base_dir: Path) -> None:
  """Ersetzt Mesh-/Textur-Dateiverweise durch ABSOLUTE Pfade (bezogen auf
  `base_dir`, das Verzeichnis der Original-Quelldatei). Noetig, weil die
  gebaute XML in `h2/xmls/` liegt -- an einem ANDEREN Ort als das Original.
  Macht das Ergebnis fest an ematalos gebunden; fuer diesen Zweck (Training
  laeuft ausschliesslich dort) akzeptabel.
  """
  compiler = root.find("compiler")
  meshdir = base_dir
  texturedir = base_dir
  if compiler is not None:
    assetdir = compiler.get("assetdir")
    if assetdir:
      meshdir = texturedir = (base_dir / assetdir).resolve()
      del compiler.attrib["assetdir"]
    if compiler.get("meshdir"):
      meshdir = (base_dir / compiler.get("meshdir")).resolve()
      del compiler.attrib["meshdir"]
    if compiler.get("texturedir"):
      texturedir = (base_dir / compiler.get("texturedir")).resolve()
      del compiler.attrib["texturedir"]

  for tag, directory in (("mesh", meshdir), ("texture", texturedir), ("hfield", texturedir)):
    for elem in root.iter(tag):
      f = elem.get("file")
      if f and not Path(f).is_absolute():
        elem.set("file", str((directory / f).resolve()))


def _is_unsupported_geom(geom: ET.Element) -> bool:
  t = geom.get("type")
  if t in MJX_UNSUPPORTED_TYPES:
    return True
  # Geom ohne explizites `type`, aber mit `mesh=`, ist implizit type="mesh".
  return t is None and geom.get("mesh") is not None


def disable_unsupported_collisions(root: ET.Element) -> int:
  count = 0
  for geom in root.iter("geom"):
    if _is_unsupported_geom(geom):
      geom.set("contype", "0")
      geom.set("conaffinity", "0")
      count += 1
  return count


def disable_all_broadphase(root: ET.Element) -> int:
  """Setzt contype=conaffinity=0 auf ALLEN Geoms -> Kollision laeuft NUR noch
  ueber die expliziten <pair>-Kontakte (G1-Muster, siehe g1_mjx_feetonly.xml
  <default> contype=0). Sonst enumeriert die MJX-Broad-Phase auch die vielen
  Fuss-Kontaktkugeln (14/Fuss) -> riesiger XLA-Graph -> Compile dauert Stunden
  (verifiziert: >2 h haengengeblieben). Mit nur den 3 Fuss<->Boden/Fuss-Pairs
  kompiliert das Trainings-Step in Minuten und laeuft deutlich schneller.
  Wirkt NICHT auf die <pair>-Eintraege (die kollidieren explizit, unabhaengig
  von contype/conaffinity)."""
  count = 0
  for geom in root.iter("geom"):
    if geom.get("contype") != "0" or geom.get("conaffinity") != "0":
      geom.set("contype", "0")
      geom.set("conaffinity", "0")
      count += 1
  return count


def _find_body(root: ET.Element, name: str) -> ET.Element:
  for b in root.iter("body"):
    if b.get("name") == name:
      return b
  raise SystemExit(f"[FEHLER] Body '{name}' in der abgeflachten XML nicht gefunden.")


def _find_joint(root: ET.Element, name: str) -> ET.Element:
  for j in root.iter("joint"):
    if j.get("name") == name:
      return j
  raise SystemExit(f"[FEHLER] Gelenk '{name}' in der abgeflachten XML nicht gefunden.")


def _find_direct_box_geom(body_elem: ET.Element) -> ET.Element:
  boxes = [g for g in body_elem.findall("geom") if g.get("type") == "box"]
  if len(boxes) != 1:
    raise SystemExit(
        f"[FEHLER] erwarte genau ein direktes Box-Geom in Body "
        f"'{body_elem.get('name')}' der abgeflachten XML, gefunden: {len(boxes)}."
    )
  return boxes[0]


def rename_site_everywhere(root: ET.Element, old_name: str, new_name: str) -> None:
  """Benennt eine Site um UND alle Referenzen darauf (Team-Vorgabe: "einfachster
  Weg: umbenennen", damit die Env-Klassen nur die G1-kompatiblen Site-Namen
  kennen muessen). Das Quellmodell hat bereits 101 Sensoren (u. a. imu_quat/
  imu_gyro/imu_acc), von denen manche vermutlich `site="<old_name>"` bzw.
  `objtype="site" objname="<old_name>"` referenzieren -- ein blosses Umbenennen
  der <site> selbst wuerde solche Referenzen als haengende Verweise zuruecklassen
  und den Compile-Schritt mit einem kryptischen MuJoCo-Fehler abbrechen lassen.
  """
  found_site = False
  for site in root.iter("site"):
    if site.get("name") == old_name:
      site.set("name", new_name)
      found_site = True
  if not found_site:
    raise SystemExit(f"[FEHLER] Site '{old_name}' in der abgeflachten XML nicht gefunden.")

  for elem in root.iter():
    if elem.get("site") == old_name:
      elem.set("site", new_name)
    if elem.get("objtype") == "site" and elem.get("objname") == old_name:
      elem.set("objname", new_name)


def _find_parent(root: ET.Element, target: ET.Element) -> Optional[ET.Element]:
  """`xml.etree.ElementTree` kennt keine Eltern-Referenz -- lineare Suche."""
  for parent in root.iter():
    for child in parent:
      if child is target:
        return parent
  return None


def extract_and_remove_floor(root: ET.Element) -> Dict[str, str]:
  """Loest das (im H2-Quellmodell bereits vorhandene) Boden-Geom 'floor' aus
  dem Roboter-XML heraus und liefert seine Original-Attribute zurueck.

  Grund (siehe Modul-Konstante `TERRAINS` oben): rough_terrain/stairs
  brauchen einen ANDEREN Boden als flat_terrain, aber alle drei sollen
  denselben `h2_mjx_feetonly.xml`-Include nutzen -- der Boden darf deshalb
  nicht mehr Teil dieser gemeinsamen Datei sein, sondern wird JE SZENE in
  `write_scene_xml` neu angelegt. Fuer flat_terrain aus den hier gesicherten
  Attributen 1:1 rekonstruiert (reine Verlagerung, keine Verhaltensaenderung).
  """
  floor = None
  for geom in root.iter("geom"):
    if geom.get("name") == "floor":
      floor = geom
      break
  if floor is None:
    raise SystemExit(
        "[FEHLER] Boden-Geom 'floor' in der abgeflachten XML nicht gefunden "
        "(sollte durch verify_and_introspect() bereits sichergestellt sein)."
    )
  parent = _find_parent(root, floor)
  if parent is None:
    raise SystemExit("[FEHLER] Eltern-Element von Boden-Geom 'floor' nicht gefunden.")
  attrs = dict(floor.attrib)
  parent.remove(floor)
  return attrs


def add_feet_sites_and_pairs(root: ET.Element, foot_geom_info: Dict) -> None:
  """Benennt die (bereits vorhandene) Sohlen-Box je Seite in 'left_foot'/
  'right_foot' um, fuegt je eine Site an derselben Stelle hinzu und deklariert
  explizite Kontakt-Paare (Fuss<->Boden, Fuss<->Fuss). Das G1-Muster (explizite
  <pair>-Eintraege statt contype/conaffinity-Breitband-Filterung) ist robust
  unabhaengig davon, welchen contype/conaffinity-Wert die Sohlen-Box urspruenglich
  hatte.
  """
  contact = root.find("contact")
  if contact is None:
    contact = ET.SubElement(root, "contact")

  for side in ("left", "right"):
    ginfo = foot_geom_info[side]
    canonical = f"{side}_foot"
    body_elem = _find_body(root, ginfo["body"])
    geom_elem = _find_direct_box_geom(body_elem)
    geom_elem.set("name", canonical)

    site = ET.SubElement(body_elem, "site")
    site.set("name", canonical)
    site.set("pos", " ".join(f"{v:.6f}" for v in ginfo["pos"]))
    site.set("size", "0.01")
    site.set("rgba", "1 0 0 1")

  for pair_name, g1, g2, condim, friction in (
      ("left_foot_floor", "left_foot", "floor", "3", "0.6 0.6"),
      ("right_foot_floor", "right_foot", "floor", "3", "0.6 0.6"),
      ("left_foot_right_foot", "left_foot", "right_foot", "1", None),
  ):
    pair = ET.SubElement(contact, "pair")
    pair.set("name", pair_name)
    pair.set("geom1", g1)
    pair.set("geom2", g2)
    pair.set("condim", condim)
    if friction:
      pair.set("friction", friction)


def rebuild_actuators(root: ET.Element, actuator_joint: Dict[str, str],
                       actuator_forcerange: Dict[str, Optional[np.ndarray]]) -> None:
  """Ersetzt den kompletten <actuator>-Block durch <position>-Aktuatoren in
  ACTUATOR_ORDER-Reihenfolge (siehe Modul-Docstring: Quelle nutzt <motor>).
  """
  old_actuator = root.find("actuator")
  if old_actuator is not None:
    root.remove(old_actuator)
  actuator_elem = ET.SubElement(root, "actuator")

  for act_name in consts.ACTUATOR_ORDER:
    joint_name = actuator_joint[act_name]
    joint_elem = _find_joint(root, joint_name)
    suffix = consts.suffix_of(act_name)
    params = JOINT_CLASS_PARAMS[suffix]

    # Reale Herstellerwerte (damping/armature) haben Vorrang -- G1-Werte nur
    # als Fallback, falls das Original keinen nennenswerten Wert traegt.
    orig_damping = float(joint_elem.get("damping", "0") or 0.0)
    orig_armature = float(joint_elem.get("armature", "0") or 0.0)
    orig_frictionloss = float(joint_elem.get("frictionloss", "0") or 0.0)
    if orig_damping < 1e-6:
      joint_elem.set("damping", str(params["damping"]))
    if orig_armature < 1e-6:
      joint_elem.set("armature", str(params["armature"]))
    if orig_frictionloss < 1e-6:
      joint_elem.set("frictionloss", str(DEFAULT_FRICTIONLOSS))
    # `range` (reale Gelenkgrenzen) NIE anfassen -- kommt unveraendert aus dem
    # Herstellermodell.

    pos = ET.SubElement(actuator_elem, "position")
    pos.set("name", act_name)
    pos.set("joint", joint_name)
    pos.set("kp", str(params["kp"]))
    pos.set("inheritrange", "1")
    frange = actuator_forcerange.get(act_name)
    if frange is not None:
      pos.set("forcerange", f"{frange[0]:.6f} {frange[1]:.6f}")


def _add_sensor(parent: ET.Element, tag: str, **attrs) -> ET.Element:
  e = ET.SubElement(parent, tag)
  for k, v in attrs.items():
    e.set(k, str(v))
  return e


def add_sensors(root: ET.Element) -> None:
  """IMU- (pelvis/torso) und Fuss-Sensoren -- der KOMPLETTE G1-Sensor-Block
  (`_g1_reference/xmls/g1_mjx_feetonly.xml`, Zeilen 457-479), nur mit den
  (umbenannten) H2-Site-Namen. `forwardvector_*`/`orientation_*` werden von
  `base.py`/`joystick.py` aktuell nicht gelesen, aber fuer volle Paritaet mit
  der Vorlage trotzdem angelegt (Team-Vorgabe: "kompletten Block nachbauen").
  Die 101 bereits vorhandenen H2-Sensoren (Team-Notiz) bleiben unangetastet --
  hier wird nur in den bestehenden <sensor>-Block hinein ERGAENZT.
  """
  sensor = root.find("sensor")
  if sensor is None:
    sensor = ET.SubElement(root, "sensor")

  frame_site = {"pelvis": consts.PELVIS_IMU_SITE, "torso": consts.TORSO_IMU_SITE}
  for frame, site in frame_site.items():
    _add_sensor(sensor, "framezaxis", name=f"upvector_{frame}", objtype="site", objname=site)
    _add_sensor(sensor, "velocimeter", name=f"local_linvel_{frame}", site=site)
    _add_sensor(sensor, "accelerometer", name=f"accelerometer_{frame}", site=site)
    _add_sensor(sensor, "gyro", name=f"gyro_{frame}", site=site)
    _add_sensor(sensor, "framelinvel", name=f"global_linvel_{frame}", objtype="site", objname=site)
    _add_sensor(sensor, "frameangvel", name=f"global_angvel_{frame}", objtype="site", objname=site)
    _add_sensor(sensor, "framexaxis", name=f"forwardvector_{frame}", objtype="site", objname=site)
    _add_sensor(sensor, "framequat", name=f"orientation_{frame}", objtype="site", objname=site)

  for side in ("left", "right"):
    foot = f"{side}_foot"
    _add_sensor(sensor, "framelinvel", name=f"{foot}_global_linvel", objtype="site", objname=foot)
    _add_sensor(sensor, "framezaxis", name=f"{foot}_upvector", objtype="site", objname=foot)
    _add_sensor(sensor, "force", name=f"{foot}_force", site=foot)


def write_sensor_xml(out_dir: Path) -> None:
  xml = """<mujoco>
  <sensor>
    <contact name="left_foot_floor_found" geom1="left_foot" geom2="floor" reduce="mindist" num="1" data="found"/>
    <contact name="right_foot_floor_found" geom1="right_foot" geom2="floor" reduce="mindist" num="1" data="found"/>
    <contact name="right_foot_left_foot_found" geom1="right_foot" geom2="left_foot" reduce="mindist" num="1" data="found"/>
  </sensor>
</mujoco>
"""
  (out_dir / "sensor.xml").write_text(xml, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Schritt 5: Keyframe "home" per Vorwaerts-Kinematik (kein Schaetzen)
# --------------------------------------------------------------------------- #

def compute_home_qpos(built_scene_path: Path, actuator_joint: Dict[str, str]):
  """Setzt Bein-Winkel aus LEG_HOME_POSE, Becken zunaechst bei z=0/aufrecht,
  berechnet per `mj_kinematics` die tiefste Sohlen-Unterkante beider Fuesse
  (Stuetzfunktion einer Box unter Rotation) und hebt das Becken exakt so weit
  an, dass beide Fuesse den Boden beruehren (+5 mm Clearance). `ctrl` wird
  NAMENSBASIERT (nicht per Slice) in ACTUATOR-Reihenfolge aufgebaut.
  """
  model = mujoco.MjModel.from_xml_path(str(built_scene_path))
  data = mujoco.MjData(model)

  qpos = np.zeros(model.nq)
  qpos[3] = 1.0  # Quaternion (w,x,y,z) = aufrecht, keine Rotation.

  for act_name in consts.ACTUATOR_ORDER:
    suffix = consts.suffix_of(act_name)
    if suffix in LEG_HOME_POSE:
      jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, actuator_joint[act_name])
      qpos[model.jnt_qposadr[jid]] = LEG_HOME_POSE[suffix]

  data.qpos[:] = qpos
  mujoco.mj_kinematics(model, data)

  lowest = np.inf
  for side in ("left", "right"):
    gid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, f"{side}_foot")
    xpos = data.geom_xpos[gid]
    xmat = data.geom_xmat[gid].reshape(3, 3)
    size = model.geom_size[gid]
    # Stuetzfunktion einer (rotierten) Box: tiefster Punkt entlang Welt- -z.
    extent_z = np.abs(xmat[2, :]) @ size
    lowest = min(lowest, xpos[2] - extent_z)

  clearance = 0.005
  pelvis_z = -lowest + clearance
  qpos[2] = pelvis_z

  ctrl_by_actuator = np.zeros(model.nu)
  for i, act_name in enumerate(consts.ACTUATOR_ORDER):
    jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, actuator_joint[act_name])
    ctrl_by_actuator[i] = qpos[model.jnt_qposadr[jid]]

  print(
      f"[build] Keyframe 'home': Becken-Hoehe z={pelvis_z:.4f} m "
      f"(tiefster Sohlenpunkt bei Becken-z=0: {lowest:.4f} m, Clearance {clearance} m) "
      "-- BITTE im Viewer kurz gegenpruefen, ob die Pose plausibel aussieht."
  )
  return qpos, ctrl_by_actuator


_SCENE_FILENAMES = {
    "flat_terrain": "scene_mjx_feetonly_flat_terrain.xml",
    "rough_terrain": "scene_mjx_feetonly_rough_terrain.xml",
    "stairs": "scene_mjx_feetonly_stairs.xml",
}


def _floor_block_xml(terrain: str, floor_attrs: Dict[str, str]) -> tuple:
  """Baut (asset_xml, floor_geom_xml) fuer die gegebene Terrain-Variante.

  - "flat_terrain": das URSPRUENGLICHE Boden-Geom (siehe
    `extract_and_remove_floor`) wird HIER 1:1 aus `floor_attrs` rekonstruiert
    -- reine Verlagerung Roboter-XML -> Szenen-XML, keine Verhaltensaenderung.
    Kein zusaetzliches <asset> noetig, falls das Original ueber `material`
    bereits auf ein Asset im (unveraendert mitgelieferten) Roboter-<asset>
    verweist.
  - "rough_terrain"/"stairs": neues Hoehenfeld-Geom (weiterhin "floor"
    genannt -- die expliziten Fuss-<pair>-Eintraege und Kontakt-Sensoren in
    `h2_mjx_feetonly.xml` referenzieren diesen Namen fest, siehe
    `add_feet_sites_and_pairs`/`write_sensor_xml`). Rocky-Textur analog G1
    (`_g1_reference/xmls/scene_mjx_feetonly_rough_terrain.xml`); die Datei
    `assets/rocky_texture.png` muss VORHER manuell von dort nach
    `xmls/assets/` kopiert werden (siehe README.md -- hier nicht automatisch
    moeglich, das Original liegt im installierten mujoco_playground-Paket).
    Kollisions-technisch macht das WIE das Boden-Geom genau aussieht ohnehin
    keinen Unterschied: die eigentlichen Fuss<->Boden-Kontakte laufen ueber
    die expliziten <pair>-Eintraege, nicht ueber contype/conaffinity.
  """
  if terrain == "flat_terrain":
    attrs_xml = " ".join(f'{k}="{v}"' for k, v in floor_attrs.items())
    return "", f"    <geom {attrs_xml}/>"

  hfield_file = "hfield_rough.png" if terrain == "rough_terrain" else "hfield_stairs.png"
  hfield_size = HFIELD_ROUGH_SIZE if terrain == "rough_terrain" else HFIELD_STAIRS_SIZE
  asset_xml = f"""
  <asset>
    <!-- Textur wie G1-Referenz (siehe _g1_reference/xmls/scene_mjx_feetonly_rough_terrain.xml,
         Quelle dort: https://polyhaven.com/a/rock_face) -- Datei manuell nach
         xmls/assets/rocky_texture.png kopieren (siehe README.md). -->
    <texture type="2d" name="terrain_rocky" file="assets/rocky_texture.png"/>
    <material name="terrain_rocky" texture="terrain_rocky" texuniform="true" texrepeat="5 5" reflectance=".8"/>
    <hfield name="hfield" file="assets/{hfield_file}" size="{hfield_size}"/>
  </asset>"""
  # Eigener Material-/Texturname (NICHT "groundplane"): das Roboter-XML
  # (h2_mjx_feetonly.xml) enthaelt bereits eine "groundplane"-Textur/-Material
  # fuers flache Terrain -> gleicher Name = "repeated name 'groundplane'".
  floor_xml = '    <geom name="floor" type="hfield" hfield="hfield" material="terrain_rocky"/>'
  return asset_xml, floor_xml


def write_scene_xml(
    out_dir: Path,
    robot_xml_name: str,
    floor_attrs: Dict[str, str],
    terrain: str = "flat_terrain",
    keyframe=None,
) -> Path:
  """Szenen-Wrapper um `h2_mjx_feetonly.xml`, JE Terrain-Variante (siehe
  Modul-Konstante `TERRAINS` oben und `_floor_block_xml` fuer den Boden-Teil).

  ABWEICHUNG von einer frueheren Fassung dieses Skripts: der Boden ("floor")
  ist NICHT MEHR Teil von `h2_mjx_feetonly.xml` (siehe
  `extract_and_remove_floor`), sondern wird HIER JE SZENE neu angelegt --
  noetig, damit rough_terrain/stairs einen anderen Boden haben koennen als
  flat_terrain, obwohl alle drei denselben Roboter-Include nutzen.
  """
  if terrain not in TERRAINS:
    raise ValueError(f"Unbekannte Terrain-Variante {terrain!r} (erlaubt: {TERRAINS})")
  asset_xml, floor_geom_xml = _floor_block_xml(terrain, floor_attrs)

  keyframe_xml = ""
  if keyframe is not None:
    qpos, ctrl = keyframe
    qpos_str = " ".join(f"{v:.6f}" for v in qpos)
    ctrl_str = " ".join(f"{v:.6f}" for v in ctrl)
    keyframe_xml = f"""
  <keyframe>
    <key name="home"
      qpos="{qpos_str}"
      ctrl="{ctrl_str}"/>
  </keyframe>
"""
  xml = f"""<mujoco model="h2 scene ({terrain})">
  <include file="{robot_xml_name}"/>

  <statistic center="0 0 0.9" extent="1.5" meansize="0.05"/>

  <visual>
    <headlight diffuse=".8 .8 .8" ambient=".2 .2 .2" specular="1 1 1"/>
    <rgba force="1 0 0 1"/>
    <global azimuth="140" elevation="-20"/>
    <map force="0.01"/>
    <scale forcewidth="0.3" contactwidth="0.5" contactheight="0.2"/>
    <quality shadowsize="8192"/>
  </visual>
{asset_xml}

  <worldbody>
{floor_geom_xml}
  </worldbody>

  <include file="sensor.xml"/>
{keyframe_xml}</mujoco>
"""
  scene_path = out_dir / _SCENE_FILENAMES[terrain]
  scene_path.write_text(xml, encoding="utf-8")
  return scene_path


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> None:
  ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  ap.add_argument(
      "source_xml", type=Path,
      help="Pfad zur H2-Quell-MJCF, z. B. ~/unitree_mujoco/unitree_robots/h2/scene.xml",
  )
  ap.add_argument(
      "--out-dir", type=Path, default=Path(__file__).resolve().parent / "xmls",
      help="Zielverzeichnis fuer die gebauten XML-Dateien (Default: h2/xmls/)",
  )
  args = ap.parse_args()

  source_xml = args.source_xml.expanduser().resolve()
  out_dir = args.out_dir
  out_dir.mkdir(parents=True, exist_ok=True)

  print(f"[build] lade Quellmodell: {source_xml}")
  model = mujoco.MjModel.from_xml_path(str(source_xml))
  print(f"[build] geladen: nq={model.nq} nv={model.nv} nu={model.nu} njnt={model.njnt}")
  if (model.nq, model.nv, model.nu, model.njnt) != (38, 37, 31, 32):
    print(
        "[build] WARNUNG: nq/nv/nu/njnt weichen von den verifizierten Werten "
        "(38/37/31/32, siehe Team-Notiz) ab -- Quelldatei hat sich evtl. "
        "geaendert, bitte pruefen, bevor dem Ergebnis vertraut wird."
    )

  info = verify_and_introspect(model)
  print(f"[build] {len(info['actuator_joint'])} Aktuatoren verifiziert (Namen siehe h2_constants.ACTUATOR_ORDER).")
  print("[build] <option> (Timestep/Solver) der Quelldatei bleibt UNVERAENDERT (siehe Modul-Docstring).")

  print("[build] erzeuge flache Kopie via MuJoCo-Compiler (loest <include> auf)...")
  flat_path = flatten_xml(source_xml)
  try:
    tree = ET.parse(flat_path)
    root = tree.getroot()

    absolutize_asset_paths(root, source_xml.parent)

    n_disabled = disable_unsupported_collisions(root)
    print(f"[build] {n_disabled} Mesh-/Zylinder-/Ellipsoid-Geoms auf contype=conaffinity=0 gesetzt.")

    # Team-Notiz: Boden-Geom heisst im Original bereits "floor" (type plane,
    # contype=1). WIRD WIEDERVERWENDET (keine neuen Attribute erfunden), aber
    # NICHT MEHR hier im Roboter-XML belassen -- siehe `extract_and_remove_floor`:
    # der Boden wird herausgeloest und JE SZENE (flat/rough/stairs) in
    # `write_scene_xml` neu angelegt, damit Terrain-Varianten einen anderen
    # Boden haben koennen, obwohl sie denselben Roboter-Include nutzen.
    floor_attrs = extract_and_remove_floor(root)
    print(f"[build] Boden-Geom 'floor' aus Roboter-XML geloest (Original-Attribute: {floor_attrs}) "
          "-- wird jetzt pro Terrain-Szene einzeln angelegt (siehe write_scene_xml).")

    rename_site_everywhere(root, SOURCE_PELVIS_IMU_SITE, consts.PELVIS_IMU_SITE)
    rename_site_everywhere(root, SOURCE_TORSO_IMU_SITE, consts.TORSO_IMU_SITE)

    add_feet_sites_and_pairs(root, info["foot_geom"])
    rebuild_actuators(root, info["actuator_joint"], info["actuator_forcerange"])
    add_sensors(root)

    # NACH dem Deklarieren der expliziten Fuss-Pairs: Broad-Phase komplett aus
    # (nur die Pairs kollidieren) -> kleiner XLA-Graph, schneller Compile.
    n_bp = disable_all_broadphase(root)
    print(f"[build] Broad-Phase-Kollision auf {n_bp} Geoms deaktiviert (nur explizite <pair>-Kontakte aktiv).")

    robot_xml_name = "h2_mjx_feetonly.xml"
    tree.write(out_dir / robot_xml_name, encoding="utf-8", xml_declaration=False)
  finally:
    flat_path.unlink(missing_ok=True)

  write_sensor_xml(out_dir)

  # Erst OHNE Keyframe schreiben (flat_terrain als Entwurf), um per echter
  # Kinematik die Becken-Hoehe zu bestimmen (compute_home_qpos braucht ein
  # ladbares, vollstaendiges Modell -- der Boden selbst spielt fuer die
  # Kinematik keine Rolle, deshalb genuegt hierfuer flat_terrain als Entwurf).
  draft_scene_path = write_scene_xml(out_dir, robot_xml_name, floor_attrs, terrain="flat_terrain", keyframe=None)
  print("[build] berechne Keyframe 'home' per Vorwaerts-Kinematik...")
  qpos, ctrl = compute_home_qpos(draft_scene_path, info["actuator_joint"])

  # DERSELBE Keyframe (terrain-unabhaengig, siehe oben) fuer alle drei
  # Varianten -- nur der Boden unterscheidet sich (siehe `_floor_block_xml`).
  scene_paths = {}
  for terrain in TERRAINS:
    scene_paths[terrain] = write_scene_xml(
        out_dir, robot_xml_name, floor_attrs, terrain=terrain, keyframe=(qpos, ctrl)
    )
    print(f"[build] Szene geschrieben: {scene_paths[terrain]}")

  print("[build] Smoke-Test: flat_terrain laden (verbindlich)...")
  final_model = mujoco.MjModel.from_xml_path(str(scene_paths["flat_terrain"]))
  print(
      f"[build] OK -- nq={final_model.nq} nv={final_model.nv} nu={final_model.nu} "
      f"nkey={final_model.nkey}"
  )

  # rough_terrain/stairs brauchen zusaetzlich die per make_hfields.py erzeugten
  # Hoehenfeld-PNGs sowie (manuell kopiert) assets/rocky_texture.png (siehe
  # README.md) -- beides existiert direkt nach diesem Build-Lauf i.d.R. noch
  # NICHT. Deshalb hier nur ein BEST-EFFORT-Smoke-Test (Warnung statt Abbruch),
  # damit ein noch fehlendes Asset nicht den gesamten Build-Lauf scheitern laesst.
  for terrain in ("rough_terrain", "stairs"):
    try:
      terrain_model = mujoco.MjModel.from_xml_path(str(scene_paths[terrain]))
      print(f"[build] Smoke-Test {terrain}: OK -- nq={terrain_model.nq} nv={terrain_model.nv} "
            f"nu={terrain_model.nu} nkey={terrain_model.nkey}")
    except Exception as exc:  # laeuft nur best-effort, siehe Kommentar oben
      print(f"[build] Smoke-Test {terrain} (noch) fehlgeschlagen ({exc}) -- "
            "vermutlich fehlen noch die Hoehenfeld-/Textur-Assets, siehe README.md "
            "(make_hfields.py ausfuehren + rocky_texture.png von der G1-Referenz kopieren).")

  print(f"[build] fertig. Ergebnis unter: {out_dir}")


if __name__ == "__main__":
  main()
