"""Konstanten fuer das H2-MJX-Trainingsmodell.

Analog zu `_g1_reference/g1_constants.py`, aber mit zwei wichtigen Abweichungen:

1) ROOT_PATH zeigt NICHT in das installierte `mujoco_playground`-Package (wie bei
   G1), sondern auf dieses lokale Verzeichnis (`training/rl/h2/`) -- H2 ist kein
   Playground-Erstanbieter-Env. Das von `build_h2_mjx_model.py` erzeugte XML
   referenziert Mesh-Dateien per ABSOLUTEM Pfad auf ematalos; ein Asset-Bundling
   wie bei G1 (`get_assets()`) ist deshalb hier nicht noetig (siehe `base.py`).

2) ALLE 31 H2-Gelenke werden ausschliesslich ueber ihren AKTUATOR-NAMEN
   (`ACTUATOR_ORDER`) adressiert, niemals per qpos-Slice `[7:]`/`[6:]` wie bei G1.
   Grund (verifiziert in `training/deploy/deploy_h2_g1policy.py`, Kommentarblock
   ab Zeile 11): die qpos-Gelenkreihenfolge im H2-Modell ist
   (Beine, Taille, KOPF, ARME), waehrend die Aktuator-/ctrl-Reihenfolge
   (Beine, Taille, ARME, KOPF) ist -- beides faellt bei G1 zufaellig zusammen,
   bei H2 NICHT. `base.py` baut daraus bei Env-Konstruktion eine explizite
   Index-Umsetzung (actuator_trnid -> jnt_qposadr/jnt_dofadr).

Die Aktuator-NAMEN selbst (z. B. "left_hip_pitch", OHNE "_joint"-Suffix wie bei
G1) sind fuer die 12 Beingelenke VERIFIZIERT (identisch aus
`deploy_h2_g1policy.py` uebernommen, dort per `mj_name2id(..., mjOBJ_ACTUATOR, ...)`
erfolgreich aufgeloest). Taille/Arme/Kopf sind nach demselben Namensschema
extrapoliert (Unitree-Konvention) -- NICHT verifiziert. `build_h2_mjx_model.py`
bricht beim Bauen mit Klartext-Fehler ab, falls ein Name nicht existiert; die
tatsaechlich vorhandenen Aktuatoren werden dann mit ausgegeben, damit die Liste
hier leicht korrigiert werden kann.
"""

from etils import epath
import numpy as np

# --- Pfade -------------------------------------------------------------------

ROOT_PATH = epath.Path(__file__).resolve().parent
FEET_ONLY_FLAT_TERRAIN_XML = ROOT_PATH / "xmls" / "scene_mjx_feetonly_flat_terrain.xml"
# Rough/Stairs analog G1 (_g1_reference/g1_constants.py: FEET_ONLY_ROUGH_TERRAIN_XML).
# Beide werden -- wie die flache Szene -- von `build_h2_mjx_model.py` erzeugt (dort
# entsteht auch der gemeinsame `home`-Keyframe, terraingleich, da Kinematik-basiert
# und unabhaengig vom Boden). Zusaetzlich braucht es vorher einmalig die per
# `make_hfields.py` erzeugten Hoehenfeld-PNGs unter `xmls/assets/` (siehe README.md).
FEET_ONLY_ROUGH_TERRAIN_XML = ROOT_PATH / "xmls" / "scene_mjx_feetonly_rough_terrain.xml"
FEET_ONLY_STAIRS_XML = ROOT_PATH / "xmls" / "scene_mjx_feetonly_stairs.xml"

# G1-Gangreferenz fuer den Imitations-Reward (siehe joystick.py + extract_g1_reference.py).
# Optional -- existiert erst nach einem Lauf von extract_g1_reference.py (auf ematalos,
# braucht die trainierte G1-Policy). Solange die Datei fehlt bleibt der Reward-Term
# inaktiv (siehe joystick.py::_post_init).
GAIT_REFERENCE_DIR = ROOT_PATH / "assets"
G1_GAIT_REFERENCE_NPY = GAIT_REFERENCE_DIR / "g1_gait_reference.npy"
G1_GAIT_REFERENCE_META_JSON = GAIT_REFERENCE_DIR / "g1_gait_reference.json"


def task_to_xml(task_name: str) -> epath.Path:
  """'flat_terrain' (Standard), 'rough_terrain' und 'stairs' verfuegbar.

  Rough/Stairs sind BLIND (keine Hoehenkarten-Beobachtung, siehe joystick.py-
  Modul-Docstring) -- reine Boden-Variation, keine Env-Logik-Aenderung.
  Solange `make_hfields.py` + der entsprechende Build-Lauf nicht ausgefuehrt
  wurden, existieren die Dateien noch nicht; das Laden schlaegt dann mit einem
  regulaeren "Datei nicht gefunden"-Fehler von MuJoCo fehl (kein Sonderfall
  hier noetig).
  """
  return {
      "flat_terrain": FEET_ONLY_FLAT_TERRAIN_XML,
      "rough_terrain": FEET_ONLY_ROUGH_TERRAIN_XML,
      "stairs": FEET_ONLY_STAIRS_XML,
  }[task_name]


# --- Sites / Geoms / Bodies (von build_h2_mjx_model.py SELBST angelegt bzw. ---
# --- laut Team-Notiz im Original-H2-Modell verifiziert vorhanden) ------------

FEET_SITES = ["left_foot", "right_foot"]
LEFT_FEET_GEOMS = ["left_foot"]
RIGHT_FEET_GEOMS = ["right_foot"]
FEET_GEOMS = LEFT_FEET_GEOMS + RIGHT_FEET_GEOMS

# Verifiziert (Team-Notiz): waist_yaw_link/waist_roll_link -> torso_link.
ROOT_BODY = "torso_link"

# Im Original-Modell heissen die IMU-Sites "imu" (auf pelvis) und
# "secondary_imu" (auf torso_link) (Team-Notiz). `build_h2_mjx_model.py`
# benennt sie beim Bauen -- INKLUSIVE aller Referenzen, auch der 101 bereits
# vorhandenen H2-Sensoren -- auf die G1-kompatiblen Namen unten um (Team-
# Vorgabe: "einfachster Weg: umbenennen", damit keine Env-Klasse einen
# H2-Sonderfall fuer Site-Namen braucht). Der Rest des Codes (base.py,
# joystick.py) kennt nur diese beiden Konstanten, nie die Original-Namen.
PELVIS_IMU_SITE = "imu_in_pelvis"
TORSO_IMU_SITE = "imu_in_torso"

GRAVITY_SENSOR = "upvector"
GLOBAL_LINVEL_SENSOR = "global_linvel"
GLOBAL_ANGVEL_SENSOR = "global_angvel"
LOCAL_LINVEL_SENSOR = "local_linvel"
ACCELEROMETER_SENSOR = "accelerometer"
GYRO_SENSOR = "gyro"
# Sensor-NAMEN-Suffixe (nicht die Site-Namen!) -- "pelvis" -> Site
# `imu_in_pelvis`, "torso" -> Site `imu_in_torso`. So bleiben
# get_gravity(data, "torso")-artige Aufrufe aus der G1-Vorlage 1:1
# wiederverwendbar.
IMU_FRAMES = ("pelvis", "torso")

# --- Aktuator-Reihenfolge (== d.ctrl-Reihenfolge) -----------------------------
# Bein-Suffixe VERIFIZIERT (Team-Notiz + deploy_h2_g1policy.py). H2-Knoechel:
# ankle_roll VOR ankle_pitch (bei G1 ist es umgekehrt!).
_LEG_SUFFIXES = ["hip_pitch", "hip_roll", "hip_yaw", "knee", "ankle_roll", "ankle_pitch"]
# Taille: yaw, roll, pitch (Team-Notiz, wie bei G1).
_WAIST_SUFFIXES = ["waist_yaw", "waist_roll", "waist_pitch"]
# Arm-Reihenfolge wie G1 uebernommen (Team-Notiz nennt dieselbe Reihenfolge).
_ARM_SUFFIXES = [
    "shoulder_pitch", "shoulder_roll", "shoulder_yaw", "elbow",
    "wrist_roll", "wrist_pitch", "wrist_yaw",
]
# Kopf: KEIN G1-Vorbild, neu bei H2 -- Reihenfolge laut Team-Notiz.
_HEAD_SUFFIXES = ["head_pitch", "head_yaw"]

ACTUATOR_ORDER = (
    [f"left_{s}" for s in _LEG_SUFFIXES]
    + [f"right_{s}" for s in _LEG_SUFFIXES]
    + list(_WAIST_SUFFIXES)
    + [f"left_{s}" for s in _ARM_SUFFIXES]
    + [f"right_{s}" for s in _ARM_SUFFIXES]
    + list(_HEAD_SUFFIXES)
)
assert len(ACTUATOR_ORDER) == 31, f"Erwarte 31 Aktuatoren, habe {len(ACTUATOR_ORDER)}"


def suffix_of(actuator_name: str) -> str:
  """'left_hip_pitch' -> 'hip_pitch'; 'waist_yaw' -> 'waist_yaw' (keine Seite)."""
  for side in ("left_", "right_"):
    if actuator_name.startswith(side):
      return actuator_name[len(side):]
  return actuator_name


# --- Index-Gruppen fuer Reward-Terme (Index IN ACTUATOR_ORDER, kein qpos-Index!) --
# Reihenfolge je Gruppe bewusst identisch zur G1-Vorlage aufgebaut (Seite aussen,
# Gelenk innen), damit z. B. das hartkodierte Gewichts-Array in
# `_cost_joint_deviation_hip` (siehe joystick.py) unveraendert uebernommen werden kann.

def _actuator_indices(names: list) -> np.ndarray:
  return np.array([ACTUATOR_ORDER.index(n) for n in names], dtype=np.int32)


WAIST_ACTUATORS = list(_WAIST_SUFFIXES)
ARM_ACTUATORS = [f"left_{s}" for s in _ARM_SUFFIXES] + [f"right_{s}" for s in _ARM_SUFFIXES]
HIP_ROLL_YAW_ACTUATORS = [
    f"{side}_{s}" for side in ("left", "right") for s in ("hip_roll", "hip_yaw")
]
KNEE_ACTUATORS = ["left_knee", "right_knee"]

WAIST_INDICES = _actuator_indices(WAIST_ACTUATORS)
ARM_INDICES = _actuator_indices(ARM_ACTUATORS)
HIP_ROLL_YAW_INDICES = _actuator_indices(HIP_ROLL_YAW_ACTUATORS)
KNEE_INDICES = _actuator_indices(KNEE_ACTUATORS)

# Fuer den Imitations-Reward (siehe joystick.py): die 6 Bein-Gelenke JE SEITE, in
# genau dieser Reihenfolge -- das ist auch die Spaltenreihenfolge der G1-Gang-
# referenztabelle (siehe extract_g1_reference.py, dort bereits von G1- auf diese
# H2-Reihenfolge retargetiert, inkl. Knoechel-Swap).
LEG_JOINT_ORDER = tuple(_LEG_SUFFIXES)
LEFT_LEG_ACTUATORS = [f"left_{s}" for s in _LEG_SUFFIXES]
RIGHT_LEG_ACTUATORS = [f"right_{s}" for s in _LEG_SUFFIXES]
LEFT_LEG_INDICES = _actuator_indices(LEFT_LEG_ACTUATORS)
RIGHT_LEG_INDICES = _actuator_indices(RIGHT_LEG_ACTUATORS)

# fmt: off
# Pose-Gewichte je Aktuator -- identische Systematik wie G1 (kleine Gewichtung fuer
# hip_pitch/knee, da fuer den Gang aktiv gebraucht). HINWEIS: In der G1-Referenz
# (`_g1_reference/joystick.py`) wird dieses Array aufgebaut, aber von KEINER
# `_cost_*`-Funktion tatsaechlich gelesen -- vermutlich Ueberbleibsel einer
# frueheren Reward-Variante. Hier nur zur strukturellen Paritaet mit der Vorlage
# uebernommen (verfuegbar fuer eine spaetere gewichtete Pose-Kost).
POSE_WEIGHTS = np.array(
    [0.01, 1.0, 1.0, 0.01, 1.0, 1.0] * 2  # linkes + rechtes Bein (hip_p,hip_r,hip_y,knee,ank_r,ank_p)
    + [1.0, 1.0, 1.0]                      # Taille
    + [1.0] * 7 * 2                         # Arme
    + [1.0, 1.0],                           # Kopf
    dtype=np.float32,
)
# fmt: on
assert POSE_WEIGHTS.shape[0] == 31


def restricted_joint_range(raw_range: np.ndarray, factor: float = 0.9) -> np.ndarray:
  """Schrumpft reale Gelenkgrenzen sicherheitshalber um `factor` (Mittelpunkt fix).

  Im Gegensatz zu G1 (wo `RESTRICTED_JOINT_RANGE` datenblattbasierte Literalwerte
  sind) gibt es fuer H2 keine verifizierten Sicherheitsgrenzen. Deshalb wird HIER
  zur Laufzeit (siehe `base.py`) aus den ECHTEN, aus dem H2-Modell gelesenen
  `jnt_range`-Werten ein `factor`-Fenster um die Gelenkmitte abgeleitet, statt
  Zahlen zu erfinden. `raw_range` hat Form (..., 2) = (lower, upper).
  """
  raw_range = np.asarray(raw_range, dtype=np.float64)
  center = raw_range.mean(axis=-1)
  half_span = (raw_range[..., 1] - raw_range[..., 0]) * 0.5 * factor
  return np.stack([center - half_span, center + half_span], axis=-1)
