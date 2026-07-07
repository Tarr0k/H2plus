"""make_hfields.py -- erzeugt die Hoehenfeld-PNGs (Heightfields) fuer die
H2-Terrain-Varianten "rough_terrain" und "stairs" (siehe `h2_constants.py`,
`build_h2_mjx_model.py`).

LAEUFT SPAETER AUF EMATALOS (braucht nur numpy + Pillow, KEIN echtes `mujoco`-
Package). Wird NICHT von Claude ausgefuehrt -- nur geschrieben.

MuJoCo-<hfield>-Grundlagen (siehe MuJoCo-XML-Referenz, Abschnitt "hfield"):
ein <hfield file="..."/> erwartet ein Graustufenbild (0..255, hier 8-bit "L").
Das dazugehoerige `size`-Attribut ("radius_x radius_y elevation_z base_z",
Meter) legt fest:
  - `radius_x`/`radius_y`: halbe Ausdehnung des Feldes in X/Y (das Bild deckt
    also ein Quadrat/Rechteck von `2*radius_x` x `2*radius_y` Metern ab).
  - `elevation_z`: die Hoehe (Meter), der GRAUSTUFE 255 im Bild entspricht
    (Graustufe 0 = Boden-Nullniveau).
  - `base_z`: zusaetzliche Sockeltiefe unterhalb der niedrigsten Stelle (rein
    fuer ein solides Fundament, ohne Einfluss auf die Hoehenkarte selbst).

WICHTIG -- KEINE automatische Kopplung zu den Szenen-XMLs: die
`elevation_z`-Werte in `build_h2_mjx_model.py` (`HFIELD_ROUGH_SIZE`/
`HFIELD_STAIRS_SIZE`) MUESSEN manuell mit `ROUGH_MAX_HEIGHT_M`/
`STAIRS_MAX_HEIGHT_M` HIER uebereinstimmen -- sonst zeigt die reale Simulation
eine andere Wellenhoehe/Stufenhoehe als hier dokumentiert. Ebenso muss
`HFIELD_HALF_EXTENT_M` HIER mit `radius_x`/`radius_y` dort uebereinstimmen.
Bei Aenderung an einer Stelle IMMER auch die andere anpassen.

Aufruf (auf ematalos):
    ~/mjxenv/bin/python make_hfields.py
    # schreibt nach training/rl/h2/xmls/assets/hfield_rough.png
    #                                        /hfield_stairs.png
Idempotent (fester Seed fuer `rough`, `stairs` ist ohnehin deterministisch) --
mehrfaches Ausfuehren erzeugt byte-identische PNGs.

UNVERIFIZIERT (siehe README.md, Abschnitt "Terrain-Varianten"): ob MuJoCo
Bild-Zeile 0 auf die hier angenommene Weltkoordinate (-radius_y) mappt. Fuer
"stairs" wichtig, damit der Roboter (spawnt nahe Weltursprung, siehe
`H2JoystickFlatTerrain.reset`) VOR der ersten Stufe steht statt mitten auf
oder hinter der Treppe -- nach dem ersten Bauen unbedingt im Viewer
gegenpruefen, ggf. `np.flipud` in `make_stairs()` ergaenzen.

Folgeschritt (noch NICHT implementiert): eine echte Hoehenkarten-Beobachtung
(z. B. ein lokales Sample-Gitter um die Fuesse/den Torso, wie es Playground
fuer "perceptive" Varianten nutzt) waere fuer zielgerichtetes Treppensteigen
langfristig noetig -- die aktuelle Env bleibt BLIND (kein Terrain in der
Beobachtung), analog `G1JoystickRoughTerrain` (siehe `joystick.py`-Docstring).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

OUT_DIR = Path(__file__).resolve().parent / "xmls" / "assets"

# --- Gemeinsame Geometrie (MUSS mit build_h2_mjx_model.py::HFIELD_*_SIZE
# uebereinstimmen, radius_x/radius_y-Teil) --------------------------------- #
HFIELD_HALF_EXTENT_M = 10.0  # -> size="10 10 ..." in den Szenen-XMLs.

# --- Rough Terrain ---------------------------------------------------------- #
ROUGH_RESOLUTION_PX = 256      # quadratisches Bild (Breite = Hoehe)
ROUGH_MAX_HEIGHT_M = 0.06      # MUSS == elevation_z in HFIELD_ROUGH_SIZE sein
ROUGH_BLUR_RADIUS_PX = 6       # Box-Blur-Radius je Durchgang
ROUGH_BLUR_PASSES = 3          # mehrfacher Box-Blur ~ Gauss-Naeherung (nur numpy)
ROUGH_SEED = 0                 # fester Seed -> reproduzierbares PNG

# --- Stairs ------------------------------------------------------------------ #
STAIRS_RESOLUTION_PX = 512     # feiner aufgeloest als rough (schaerfere Stufenkanten)
STEP_HEIGHT_M = 0.15           # Stufenhoehe (Team-Vorgabe-Bereich: 0.10-0.17 m)
STEP_DEPTH_M = 0.28            # Stufentiefe (Trittstufe), Team-Vorgabe
N_STEPS = 6                    # Anzahl Stufen aufwaerts (= Anzahl Stufen abwaerts)
STAIRS_MAX_HEIGHT_M = N_STEPS * STEP_HEIGHT_M  # 0.90 m -- MUSS == elevation_z in HFIELD_STAIRS_SIZE sein
PLATEAU_DEPTH_M = 1.0          # ebene Flaeche zwischen Auf- und Abstieg
# Anlauf-Flaeche VOR der ersten Stufe: bewusst == HFIELD_HALF_EXTENT_M gewaehlt,
# damit die erste Stufe genau bei Bild-Tiefe = HFIELD_HALF_EXTENT_M beginnt --
# das entspricht (unter der o.g. unverifizierten Zeile-0-Annahme) der WELT-
# KOORDINATE 0, also ungefaehr dort, wo der Roboter spawnt (siehe
# `H2JoystickFlatTerrain.reset`: Spawn-Offset nur +-0.5 m um den Ursprung).
APPROACH_DEPTH_M = HFIELD_HALF_EXTENT_M


def _box_blur(img: np.ndarray, radius: int, passes: int) -> np.ndarray:
  """Einfacher separabler Box-Blur, NUR mit numpy (kein scipy erlaubt).

  Mehrere Durchgaenge eines Box-Filters naehern (zentraler Grenzwertsatz)
  einen Gauss-Filter an -- ausreichend fuer sanft gewelltes Terrain, ohne
  zusaetzliche Abhaengigkeit. Rand-Handling per Kantenwiederholung ("edge"),
  damit die Raender nicht kuenstlich in Richtung 0 abgedunkelt werden.
  """
  out = img.astype(np.float64)
  kernel_size = 2 * radius + 1
  for _ in range(passes):
    for axis in (0, 1):
      pad_width = [(0, 0), (0, 0)]
      pad_width[axis] = (radius, radius)
      padded = np.pad(out, pad_width, mode="edge")
      cumsum = np.cumsum(padded, axis=axis)
      cumsum = np.insert(cumsum, 0, 0.0, axis=axis)
      n = out.shape[axis]
      if axis == 0:
        out = (cumsum[kernel_size : kernel_size + n] - cumsum[0:n]) / kernel_size
      else:
        out = (cumsum[:, kernel_size : kernel_size + n] - cumsum[:, 0:n]) / kernel_size
  return out


def make_rough(
    resolution: int = ROUGH_RESOLUTION_PX,
    seed: int = ROUGH_SEED,
    blur_radius: int = ROUGH_BLUR_RADIUS_PX,
    blur_passes: int = ROUGH_BLUR_PASSES,
) -> np.ndarray:
  """Zufaelliges, geglaettetes Wellen-Terrain als Graustufenbild (uint8)."""
  rng = np.random.default_rng(seed)
  noise = rng.uniform(0.0, 1.0, size=(resolution, resolution))
  smooth = _box_blur(noise, radius=blur_radius, passes=blur_passes)
  # Auf die volle 0..255-Spannbreite normieren, damit ROUGH_MAX_HEIGHT_M
  # (Graustufe 255) tatsaechlich einmal erreicht wird.
  smooth -= smooth.min()
  peak = smooth.max()
  if peak > 1e-9:
    smooth /= peak
  return np.clip(smooth * 255.0, 0, 255).astype(np.uint8)


def make_stairs(
    resolution: int = STAIRS_RESOLUTION_PX,
    half_extent_m: float = HFIELD_HALF_EXTENT_M,
    step_height_m: float = STEP_HEIGHT_M,
    step_depth_m: float = STEP_DEPTH_M,
    n_steps: int = N_STEPS,
    plateau_depth_m: float = PLATEAU_DEPTH_M,
    approach_depth_m: float = APPROACH_DEPTH_M,
) -> np.ndarray:
  """Treppenmuster als Graustufenbild (uint8): Anlauf (Hoehe 0) -> `n_steps`
  Stufen aufwaerts -> Plateau -> `n_steps` Stufen abwaerts -> Rest der
  Flaeche bleibt auf Hoehe 0 (Auslauf).

  Bild-ZEILEN (erste Array-Achse) sind die TIEFENRICHTUNG der Treppe (Zeile 0
  = Anlauf-Beginn, siehe `APPROACH_DEPTH_M`-Kommentar oben zur angenommenen
  Weltkoordinaten-Zuordnung -- UNVERIFIZIERT, siehe Modul-Docstring). Bild-
  SPALTEN (zweite Achse) sind die Breite der Treppe -- Hoehe ist ueber die
  gesamte Breite konstant, der Roboter kann die Treppe also unabhaengig von
  seiner seitlichen Position besteigen.
  """
  full_extent_m = 2.0 * half_extent_m
  px_per_m = resolution / full_extent_m
  max_height_m = n_steps * step_height_m

  # Hoehen-Stufenprofil entlang der Tiefenachse als Liste von (Tiefe_am_Ende_m,
  # Hoehe_AB_diesem_Punkt_m) -- die Hoehe VOR dem jeweiligen Segment-Ende gilt
  # (Treppenstufen sind Spruenge, kein Verlauf).
  segments_m: list[tuple[float, float]] = []
  depth = approach_depth_m
  segments_m.append((depth, 0.0))  # Anlauf: Hoehe 0 bis zur ersten Stufe.
  for i in range(1, n_steps + 1):
    depth += step_depth_m
    segments_m.append((depth, i * step_height_m))
  depth += plateau_depth_m
  segments_m.append((depth, max_height_m))
  for i in range(1, n_steps + 1):
    depth += step_depth_m
    segments_m.append((depth, max_height_m - i * step_height_m))
  total_depth_m = depth

  if total_depth_m > full_extent_m:
    raise SystemExit(
        f"[make_hfields] Treppen-Profil ({total_depth_m:.2f} m) passt nicht in die "
        f"hfield-Ausdehnung ({full_extent_m:.2f} m) -- half_extent_m erhoehen oder "
        "Stufenanzahl/-tiefe/Plateau/Anlauf verkleinern."
    )
  print(
      f"[make_hfields] Treppen-Profil: {n_steps} Stufen x {step_height_m:.3f} m hoch / "
      f"{step_depth_m:.3f} m tief, Gesamthoehe {max_height_m:.3f} m, "
      f"Gesamttiefe {total_depth_m:.2f} m von {full_extent_m:.2f} m verfuegbar."
  )

  row_depth_m = np.arange(resolution) / px_per_m  # Zeilenindex -> Meter (0-basiert).
  height_per_row_m = np.zeros(resolution)  # Default 0 -- deckt Anlauf VOR Segment 0 und Auslauf NACH dem letzten Segment ab.
  seg_start_depth_m, seg_height_m = 0.0, 0.0
  for seg_end_depth_m, seg_end_height_m in segments_m:
    mask = (row_depth_m >= seg_start_depth_m) & (row_depth_m < seg_end_depth_m)
    height_per_row_m[mask] = seg_height_m
    seg_start_depth_m, seg_height_m = seg_end_depth_m, seg_end_height_m

  heightmap_m = np.broadcast_to(height_per_row_m[:, np.newaxis], (resolution, resolution))
  gray = np.clip(heightmap_m / max_height_m * 255.0, 0, 255)
  return gray.astype(np.uint8)


def main() -> None:
  OUT_DIR.mkdir(parents=True, exist_ok=True)

  rough = make_rough()
  rough_path = OUT_DIR / "hfield_rough.png"
  Image.fromarray(rough, mode="L").save(rough_path)
  print(f"[make_hfields] geschrieben: {rough_path} ({rough.shape[1]}x{rough.shape[0]} px, "
        f"elevation_z={ROUGH_MAX_HEIGHT_M} m -- MUSS mit HFIELD_ROUGH_SIZE in "
        "build_h2_mjx_model.py uebereinstimmen)")

  stairs = make_stairs()
  stairs_path = OUT_DIR / "hfield_stairs.png"
  Image.fromarray(stairs, mode="L").save(stairs_path)
  print(f"[make_hfields] geschrieben: {stairs_path} ({stairs.shape[1]}x{stairs.shape[0]} px, "
        f"elevation_z={STAIRS_MAX_HEIGHT_M} m -- MUSS mit HFIELD_STAIRS_SIZE in "
        "build_h2_mjx_model.py uebereinstimmen)")

  print("[make_hfields] fertig. Fehlt noch (siehe README.md): assets/rocky_texture.png "
        "manuell von der G1-Referenz kopieren.")


if __name__ == "__main__":
  main()
