"""extract_g1_reference.py -- zeichnet einen G1-Referenzgang auf und retargetet ihn
auf H2 fuer den Imitations-Reward in `joystick.py` (siehe dessen Modul-Docstring).

Laeuft auf ematalos (braucht die trainierte G1-Policy + kurz die GPU, siehe
`training/deploy/deploy_playground_policy.py`, dessen Lade-/Restore-Logik hier
wiederverwendet wird). Ablauf:

  1. Trainierte G1-Policy laden (`~/h2_rl_runs/g1_full/best`) und im G1-Env fuer
     einen STETIGEN Vorwaertsgang ausrollen (Kommando fest, nicht die uebliche
     Zufalls-Resample-Logik der Env -- siehe `_rollout_g1`).
  2. Pro Schritt die 12 Bein-Gelenkwinkel (in G1-Reihenfolge, NAMENSBASIERT
     abgegriffen -- kein `qpos[7:]`-Sonderfall wie bei H2, aber sicherer als ihn
     stillschweigend vorauszusetzen) + die Gangphase (`state.info["phase"]`)
     aufzeichnen.
  3. Nach Phase binnen (zirkular in [-pi, pi)) UND mitteln -- linkes UND rechtes
     Bein liefern beide Stichproben fuer DIESELBE Phase->Gelenkwinkel-Funktion
     (siehe `_bin_reference`-Docstring; identisches Prinzip wie `gait.get_rz` in
     der G1-Vorlage, das Fusshoehen ebenfalls ueber eine gemeinsame Funktion der
     JEWEILS EIGENEN Beinphase erzeugt).
  4. Auf H2-Gelenkreihenfolge retargeten (Knoechel-Swap, siehe
     `h2_constants.LEG_JOINT_ORDER`) und als `.npy` + Metadaten-`.json` unter
     `h2_constants.GAIT_REFERENCE_DIR` speichern.

Aufruf (auf ematalos, analog deploy_playground_policy.py):
    XLA_PYTHON_CLIENT_ALLOCATOR=platform python training/rl/h2/extract_g1_reference.py \
        --ckpt ~/h2_rl_runs/g1_full/best --steps 4000 --vx 0.5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Muss VOR dem ersten `import jax` gesetzt sein (siehe deploy_playground_policy.py):
# nur den tatsaechlich benoetigten VRAM belegen, damit der kurze G1-Rollout neben
# einem parallel laufenden H2-Training (h2_full) in die freien VRAM-Reste passt.
os.environ.setdefault("XLA_PYTHON_CLIENT_ALLOCATOR", "platform")
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.15")

_HERE = Path(__file__).resolve()
# WICHTIG: flache Imports statt relativer (`from . import ...`) -- dieses Skript wird
# per `python extract_g1_reference.py` direkt ausgefuehrt (siehe Aufruf oben), hat
# also KEINEN Paketkontext (analog `build_h2_mjx_model.py`, gleiches Muster).
sys.path.insert(0, str(_HERE.parent))  # .../training/rl/h2 (fuer h2_constants)
sys.path.insert(0, str(_HERE.parents[1]))  # .../training/rl (fuer train_playground)
sys.path.insert(0, str(_HERE.parents[2] / "deploy"))  # .../training/deploy (fuer _build_policy)

import h2_constants as consts  # noqa: E402 -- H2-Zielreihenfolge fuers Retargeting.
import train_playground as tp  # noqa: E402
from deploy_playground_policy import _build_policy  # noqa: E402

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402

N_BINS_DEFAULT = 32

# G1-Beinreihenfolge PRO SEITE, verifiziert aus `training/deploy/deploy_h2_g1policy.py`
# (Kommentar zu POLICY_LEG_JOINTS, Quelle: unitree_rl_gym deploy/deploy_mujoco/configs/g1.yaml).
# ACHTUNG: bei G1 ankle_pitch VOR ankle_roll -- bei H2 ist es umgekehrt (siehe
# h2_constants.py-Modul-Docstring); der Swap passiert unten explizit in `_retarget_to_h2`.
G1_LEG_SUFFIXES = ["hip_pitch", "hip_roll", "hip_yaw", "knee", "ankle_pitch", "ankle_roll"]


def _leg_qpos_adr(mj_model) -> tuple[np.ndarray, np.ndarray]:
  """qpos-Adressen der 6 Bein-Gelenke je Seite, NAMENSBASIERT (G1-Reihenfolge).

  Nutzt dasselbe Joint-Namensschema `f"{side}_{suffix}_joint"`, das die G1-
  Referenz-Env fuer hip_roll/hip_yaw/knee bereits verwendet (siehe
  `_g1_reference/joystick.py::_post_init`, `_hip_indices`/`_knee_indices`) --
  hier auf alle 6 Bein-Suffixe je Seite ausgedehnt. Bricht mit Klartext-Fehler
  ab, falls ein Name nicht existiert (Namenskonvention doch nicht wie erwartet).
  """
  def adr(side: str) -> np.ndarray:
    out = []
    for suffix in G1_LEG_SUFFIXES:
      joint_name = f"{side}_{suffix}_joint"
      try:
        out.append(int(mj_model.joint(joint_name).qposadr[0]))
      except KeyError as exc:
        raise SystemExit(
            f"[extract] Gelenk '{joint_name}' nicht im G1-Modell gefunden -- "
            "Namenskonvention aus deploy_h2_g1policy.py stimmt hier nicht. "
            f"({exc})"
        ) from exc
    return np.array(out, dtype=np.int64)

  return adr("left"), adr("right")


def _rollout_g1(env, policy, steps: int, warmup: int, cmd: jax.Array, seed: int = 0):
  """Rollt die G1-Policy mit FESTEM Kommando aus; zeichnet Phase + Beinwinkel auf.

  `cmd` wird nach jedem `reset()`/`step()` explizit zurueckgesetzt -- die G1-Env
  wuerde sonst nach 500 Schritten intern ein neues Zufallskommando ziehen (siehe
  `_g1_reference/joystick.py::step`). Bei einem Sturz (`state.done`) wird neu
  gestartet, damit die Aufzeichnung nicht abreisst (nur als Warnung vermerkt --
  eine konvergierte G1-Policy sollte hier eigentlich nicht stuerzen).
  """
  reset = jax.jit(env.reset)
  step = jax.jit(env.step)
  inference = jax.jit(policy)

  left_qadr, right_qadr = _leg_qpos_adr(env.mj_model)

  rng = jax.random.PRNGKey(seed)
  rng, key = jax.random.split(rng)
  state = reset(key)
  state.info["command"] = cmd

  phases, left_qs, right_qs = [], [], []
  n_falls = 0
  for i in range(steps):
    rng, key = jax.random.split(rng)
    action, _ = inference(state.obs, key)
    state = step(state, action)
    # Kommando fest halten (siehe Docstring) -- ueberschreibt eine evtl. interne
    # Resample-Entscheidung von `step()` fuer die NAECHSTE Iteration.
    state.info["command"] = cmd

    if float(state.done) > 0.5:
      n_falls += 1
      rng, key = jax.random.split(rng)
      state = reset(key)
      state.info["command"] = cmd
      continue

    if i < warmup:
      continue  # Einschwingphase (Start aus der Home-Pose) nicht mit aufzeichnen.

    qpos = np.array(state.data.qpos)
    phases.append(np.array(state.info["phase"]))
    left_qs.append(qpos[left_qadr])
    right_qs.append(qpos[right_qadr])

  if n_falls:
    print(f"[extract] WARNUNG: G1-Policy ist {n_falls}x gestuerzt und wurde neu "
          "gestartet -- Referenz enthaelt dadurch mehrere Gangsegmente statt "
          "eines durchgehenden Laufs (sollte bei einer konvergierten Policy "
          "selten/nie vorkommen).")
  if not phases:
    raise SystemExit(f"[extract] Keine Stichproben aufgezeichnet (steps={steps}, warmup={warmup}) "
                      "-- warmup muss kleiner als steps sein.")
  return np.array(phases), np.array(left_qs), np.array(right_qs), n_falls


def _bin_reference(phases: np.ndarray, left_qs: np.ndarray, right_qs: np.ndarray,
                   n_bins: int) -> tuple[np.ndarray, np.ndarray]:
  """Baut die phasenindizierte Referenztabelle (G1-Beinreihenfolge, 6 Spalten).

  `phases` hat Shape (T, 2) -- pro Zeitschritt ein Phasenwert je Bein (versetzt
  um pi, siehe Phasenkonvention in `joystick.py::reset`/`step`). Linkes UND
  rechtes Bein werden hier als Stichproben DERSELBEN Phase->Gelenkwinkel-Funktion
  behandelt (verdoppelt effektiv die Stichprobenzahl je Bin) -- das ist exakt das
  Prinzip, nach dem auch `gait.get_rz(phase, ...)` in der G1-Vorlage die Soll-
  Fusshoehe fuer beide Fuesse aus EINER gemeinsamen Funktion ableitet.
  """
  phases_all = np.concatenate([phases[:, 0], phases[:, 1]])
  legs_all = np.concatenate([left_qs, right_qs], axis=0)
  phases_all = np.mod(phases_all + np.pi, 2 * np.pi) - np.pi  # nach [-pi, pi) normalisieren.

  bin_edges = np.linspace(-np.pi, np.pi, n_bins + 1)
  bin_idx = np.clip(np.digitize(phases_all, bin_edges) - 1, 0, n_bins - 1)

  ref = np.zeros((n_bins, legs_all.shape[1]), dtype=np.float64)
  counts = np.zeros(n_bins, dtype=np.int64)
  for b in range(n_bins):
    mask = bin_idx == b
    counts[b] = int(mask.sum())
    if counts[b] > 0:
      ref[b] = legs_all[mask].mean(axis=0)

  empty = np.where(counts == 0)[0]
  if empty.size:
    filled = np.where(counts > 0)[0]
    if filled.size == 0:
      raise SystemExit("[extract] KEIN Bin hat Stichproben -- steps/bins pruefen.")
    print(f"[extract] WARNUNG: {empty.size}/{n_bins} Phasen-Bins ohne Stichprobe "
          f"({empty.tolist()}) -- werden aus den je 2 naechsten (zirkular) gefuellten "
          "Bins gemittelt.")
    for b in empty:
      dist = np.minimum((filled - b) % n_bins, (b - filled) % n_bins)
      nearest = filled[np.argsort(dist)[:2]]
      ref[b] = ref[nearest].mean(axis=0)

  # Zirkulare 3-Bin-Glaettung -- reduziert Sampling-Rauschen (Team-Vorgabe "Signal glaetten").
  smoothed = (np.roll(ref, 1, axis=0) + ref + np.roll(ref, -1, axis=0)) / 3.0
  return smoothed, counts


def _retarget_to_h2(ref_g1_order: np.ndarray) -> np.ndarray:
  """Spalten von G1- auf H2-Beinreihenfolge ummappen (Knoechel-Swap, siehe Modul-Docstring)."""
  perm = [G1_LEG_SUFFIXES.index(s) for s in consts.LEG_JOINT_ORDER]
  return ref_g1_order[:, perm]


def main() -> None:
  ap = argparse.ArgumentParser(description="G1-Referenzgang aufzeichnen + auf H2 retargeten")
  ap.add_argument("--ckpt", type=Path, default=Path("~/h2_rl_runs/g1_full/best"),
                  help="G1-Policy-Checkpoint-Ordner (siehe deploy_playground_policy.py)")
  ap.add_argument("--env", default="G1JoystickFlatTerrain", help="i.d.R. unveraendert lassen")
  ap.add_argument("--steps", type=int, default=4000, help="Rollout-Schritte NACH Warmup (50 Hz)")
  ap.add_argument("--warmup", type=int, default=200, help="Einschwing-Schritte, nicht aufgezeichnet")
  ap.add_argument("--bins", type=int, default=N_BINS_DEFAULT, help="Anzahl Phasen-Bins")
  ap.add_argument("--vx", type=float, default=0.5, help="Sollgeschwindigkeit vorwaerts [m/s]")
  ap.add_argument("--vy", type=float, default=0.0, help="Sollgeschwindigkeit seitlich [m/s]")
  ap.add_argument("--yaw", type=float, default=0.0, help="Solldrehrate [rad/s]")
  ap.add_argument("--seed", type=int, default=0)
  ap.add_argument("--out", type=Path, default=None,
                  help="Zielordner (Default: h2_constants.GAIT_REFERENCE_DIR)")
  args = ap.parse_args()

  ckpt = args.ckpt.expanduser()
  if not ckpt.exists():
    raise SystemExit(f"[extract] Checkpoint-Ordner nicht gefunden: {ckpt}")
  out_dir = (args.out or consts.GAIT_REFERENCE_DIR).expanduser()

  print(f"[extract] JAX-Backend: {jax.default_backend()}")
  print(f"[extract] baue G1-Env ({args.env}, impl=jax) ...")
  env, _cfg = tp.build_env(args.env)
  print(f"[extract] obs={env.observation_size} act={env.action_size}")

  print(f"[extract] lade G1-Policy aus {ckpt} ...")
  policy = _build_policy(env, args.env, ckpt)

  cmd = jnp.array([args.vx, args.vy, args.yaw])
  total_steps = args.warmup + args.steps
  print(f"[extract] Rollout ueber {total_steps} Schritte (davon {args.warmup} Warmup) "
        f"mit festem Kommando {cmd.tolist()} ...")
  phases, left_qs, right_qs, n_falls = _rollout_g1(
      env, policy, total_steps, args.warmup, cmd, args.seed
  )
  print(f"[extract] {phases.shape[0]} Stichproben aufgezeichnet (x2 fuer links+rechts "
        f"= {2 * phases.shape[0]} Phase/Gelenkwinkel-Paare).")

  ref_g1_order, counts = _bin_reference(phases, left_qs, right_qs, args.bins)
  ref_h2_order = _retarget_to_h2(ref_g1_order)

  out_dir.mkdir(parents=True, exist_ok=True)
  npy_path = out_dir / "g1_gait_reference.npy"
  json_path = out_dir / "g1_gait_reference.json"
  np.save(npy_path, ref_h2_order.astype(np.float32))
  meta = {
      "n_bins": args.bins,
      "joint_order": list(consts.LEG_JOINT_ORDER),  # H2-Reihenfolge (gespeicherte Spaltenreihenfolge).
      "source_joint_order_g1": G1_LEG_SUFFIXES,
      "command": [args.vx, args.vy, args.yaw],
      "g1_checkpoint": str(ckpt),
      "g1_env": args.env,
      "steps_recorded": int(phases.shape[0]),
      "warmup_steps": args.warmup,
      "falls_during_recording": int(n_falls),
      "bin_sample_counts": counts.tolist(),
      "seed": args.seed,
  }
  with open(json_path, "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)

  print(f"[extract] Referenz gespeichert: {npy_path} (shape {ref_h2_order.shape})")
  print(f"[extract] Metadaten gespeichert: {json_path}")
  print("[extract] Fertig -- Imitations-Reward aktivieren via "
        "`train_playground.py --env H2JoystickFlatTerrain --imitation-weight 1.0 ...`")


if __name__ == "__main__":
  main()
