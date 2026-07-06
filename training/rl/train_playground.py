"""train_playground.py -- PPO-Training fuer Humanoid-Locomotion mit MuJoCo Playground + Brax.

Trainiert eine Lauf-Policy (Standard: `G1JoystickFlatTerrain`, spaeter ein
`H2...`-Env aus derselben Registry) mit Brax-PPO auf JAX/GPU. Laeuft NICHT auf
dem Windows-Entwicklungsrechner, sondern auf einem separaten Linux-Rechner mit
schwacher GPU (Quadro M4000, 8 GB VRAM, Compute 5.2) -- siehe `training/README.md`
fuer den Gesamtkontext (G1 als Vorlage, Framework-Wahl, Sim-to-Real-Pfad).

Verifizierte Rahmenbedingungen (nicht raten, siehe Kommentare im Code):
  - Playground-Envs defaulten auf `impl="warp"`, was auf der M4000 abstuerzt.
    Dieses Skript erzwingt daher IMMER `impl="jax"` (siehe `build_env`).
  - Die Playground-Default-`num_envs` (haeufig 8192) sprengen 8 GB VRAM. Die
    Anzahl ist deshalb per `--num-envs` steuerbar (Default 2048); `batch_size`
    wird automatisch konsistent mitskaliert (siehe `build_ppo_config`).

Aufruf (Beispiele):
    # Voller Trainingslauf (Tage), Checkpoints/Logs unter ~/h2_rl_runs/...
    python train_playground.py --env G1JoystickFlatTerrain

    # Rauchtest (~Minuten), z. B. um eine neue Umgebung/GPU zu pruefen
    python train_playground.py --env G1JoystickFlatTerrain --smoke

    # Unterbrochenen Lauf fortsetzen
    python train_playground.py --env G1JoystickFlatTerrain --resume

Ausgabe-Layout unter `--out-dir` (Default `~/h2_rl_runs/<env>_<seed>`):
    metrics.jsonl        -- eine JSON-Zeile pro Eval (Schritt, Reward, steps/s, ...)
    ckpt_<step>/         -- periodische Zwischen-Checkpoints (Policy-Parameter)
    best/                -- Parameter des bisher hoechsten beobachteten Rewards
    brax_native_ckpt/    -- brax-eigene orbax-Checkpoints, falls diese brax-
                             Version `save_checkpoint_path` unterstuetzt (ermoeglicht
                             echtes Resume inkl. Optimizer-Zustand/Schrittzaehler)
    final/               -- Parameter nach Trainingsende
    env_meta.json         -- Env-Name, Beobachtungs-/Aktionsgroesse, Env-Config

Policy spaeter laden/inferieren (fuer die H2-Deploy-Pipeline, analog zu
`training/deploy/deploy_h2_g1policy.py`, dort aber mit TorchScript statt JAX):
    from mujoco_playground import registry
    from brax.training.agents.ppo import networks as ppo_networks
    from brax.training.agents.ppo import train as ppo_train
    import pickle

    with open("<out-dir>/final/params.pkl", "rb") as f:   # oder orbax, siehe _load_params
        params = pickle.load(f)
    env, cfg = build_env("G1JoystickFlatTerrain")          # impl="jax" erzwingen!
    make_networks = ppo_networks.make_ppo_networks          # ggf. mit denselben
                                                              # network_factory-Kwargs
                                                              # wie beim Training
    make_inference_fn = ppo_networks.make_inference_fn(make_networks(
        env.observation_size, env.action_size))
    policy = make_inference_fn(params, deterministic=True)
    action, _ = policy(observation, rng_key)
"""
from __future__ import annotations

import argparse
import functools
import inspect
import json
import os
import pickle
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# WICHTIG: muss VOR dem ersten `import jax` gesetzt werden, sonst wirkungslos.
# Reduziert das JAX-eigene GPU-Speicher-Vorreservieren -- auf der 8-GB-M4000
# sonst schnell OOM-Kandidat, sobald noch etwas anderes (z. B. der Viewer) laeuft.
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.9")

import jax  # noqa: E402  (bewusst nach dem os.environ.setdefault oben)
import jax.numpy as _jnp  # noqa: E402


def _ensure_device_put_replicated() -> None:
    """Kompatibilitaets-Shim: brax 0.14.2 ruft zur Laufzeit
    `jax.device_put_replicated` auf, das neuere jax (hier 0.10.2) entfernt hat.
    Fuer Single-GPU-Betrieb (unser Fall) genuegt ein Broadcast auf eine fuehrende
    Geraete-Achse + `jax.device_put`. Wird VOR dem train()-Aufruf gesetzt.
    """
    def _dpr(x: Any, devices: Any) -> Any:
        n = len(devices)
        stacked = jax.tree_util.tree_map(
            lambda leaf: _jnp.broadcast_to(_jnp.asarray(leaf)[None], (n,) + _jnp.shape(leaf)),
            x,
        )
        return jax.device_put(stacked, devices[0]) if n == 1 else jax.device_put(stacked)

    jax.device_put_replicated = _dpr  # ueberschreibt den Deprecation-Stub


from mujoco_playground import registry, wrapper  # noqa: E402
from mujoco_playground.config import locomotion_params  # noqa: E402
from brax.training.agents.ppo import networks as ppo_networks  # noqa: E402
from brax.training.agents.ppo import train as ppo_train  # noqa: E402


# --------------------------------------------------------------------------- #
# Hilfsfunktionen: Config-Konvertierung, Env-/PPO-Aufbau
# --------------------------------------------------------------------------- #

def _to_plain_dict(obj: Any) -> dict:
    """ConfigDict/Mapping robust in ein reines dict wandeln (ml_collections & Co.)."""
    if hasattr(obj, "to_dict"):
        return dict(obj.to_dict())
    return dict(obj)


def _safe(fn: Callable[[], Any]) -> Any:
    """Ruft `fn()` auf und liefert None statt einer Exception (fuer optionale Metadaten)."""
    try:
        return fn()
    except Exception as exc:  # Env-Attribute sind zwischen Playground-Versionen nicht garantiert
        print(f"[warn] Metadaten-Zugriff fehlgeschlagen: {exc}")
        return None


def build_env(env_name: str):
    """Laedt ein Playground-Env und erzwingt `impl="jax"`.

    KRITISCH (verifiziert): Der Playground-Default `impl="warp"` stuerzt auf der
    Quadro M4000 (Compute 5.2) ab. Ohne dieses Erzwingen crasht das Training
    sofort beim ersten Env-Reset -- daher hier zentral und nicht optional.
    """
    cfg = registry.get_default_config(env_name)
    cfg.impl = "jax"
    env = registry.load(env_name, cfg)
    return env, cfg


def build_ppo_config(env_name: str, num_envs: int, num_timesteps: int) -> tuple[dict, Any]:
    """Baut die PPO-Kwargs (aus `locomotion_params`) + die Netzwerk-Factory.

    Nur `num_envs`, `batch_size` (daraus abgeleitet) und `num_timesteps` werden
    bewusst ueberschrieben -- alle anderen Hyperparameter kommen unveraendert aus
    `locomotion_params.brax_ppo_config`, es werden hier keine Zahlen erfunden.
    """
    raw = locomotion_params.brax_ppo_config(env_name)
    ppo_params = _to_plain_dict(raw)

    network_factory_cfg = ppo_params.pop("network_factory", None)
    if network_factory_cfg is None:
        network_factory = ppo_networks.make_ppo_networks
    elif callable(network_factory_cfg):
        # Playground liefert hier teils bereits eine fertige Factory/functools.partial.
        network_factory = network_factory_cfg
    else:
        nf_kwargs = _to_plain_dict(network_factory_cfg)
        network_factory = functools.partial(ppo_networks.make_ppo_networks, **nf_kwargs)

    # --- num_envs/batch_size an die 8-GB-M4000 anpassen -------------------------
    # Playground-Defaults (oft 8192 Envs) sprengen 8 GB VRAM, daher num_envs per
    # CLI (Default 2048, siehe parse_args). batch_size darf num_envs nicht
    # ueberschreiten und wird zusaetzlich auf ein Vielfaches von num_minibatches
    # abgerundet, damit brax die Rollout-Daten (num_envs*unroll_length) sauber in
    # batch_size*num_minibatches-Haeppchen zerlegen kann (Annahme: konservativ
    # kleiner ist auf schwacher GPU immer sicherer als exakt am Limit).
    num_minibatches = int(ppo_params.get("num_minibatches", 1)) or 1
    default_batch_size = int(ppo_params.get("batch_size", num_envs))
    batch_size = min(default_batch_size, num_envs)
    batch_size = max(num_minibatches, (batch_size // num_minibatches) * num_minibatches)

    ppo_params["num_envs"] = num_envs
    ppo_params["batch_size"] = batch_size
    ppo_params["num_timesteps"] = num_timesteps

    return ppo_params, network_factory


def _extract_reward(metrics: dict) -> Optional[float]:
    """Sucht defensiv nach dem Reward-Key -- Name variiert je nach Playground-/brax-Version."""
    candidates = (
        "eval/episode_reward",
        "eval/episode_sum_reward",
        "eval/episode_reward_mean",
        "env/episode/sum_reward",
        "episode_reward",
    )
    for key in candidates:
        if key in metrics:
            try:
                return float(metrics[key])
            except (TypeError, ValueError):
                pass
    for key, value in metrics.items():
        if "reward" in key.lower():
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


# --------------------------------------------------------------------------- #
# Checkpointing (orbax -> pickle-Fallback, damit ein fehlendes/anderes orbax
# den Trainingslauf nicht abbricht -- nur die Robustheit der Ablage leidet)
# --------------------------------------------------------------------------- #

def _save_params(path: Path, params: Any) -> None:
    """Policy-Parameter robust ablegen: erst orbax, sonst pickle-Fallback."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        import orbax.checkpoint as ocp  # lokal importieren: optionale Abhaengigkeit

        checkpointer = ocp.PyTreeCheckpointer()
        target = str((path / "params").resolve())
        if os.path.exists(target):
            shutil.rmtree(target)  # orbax verlangt i.d.R. ein nicht existierendes Ziel
        checkpointer.save(target, jax.device_get(params))
        return
    except Exception as exc:  # Version-/API-Drift bei orbax abfangen
        print(f"[ckpt] orbax-Save fehlgeschlagen ({exc}); Fallback auf pickle")
    try:
        with open(path / "params.pkl", "wb") as f:
            pickle.dump(jax.device_get(params), f)
    except Exception as exc:
        print(f"[ckpt] FEHLER: Parameter konnten nicht gespeichert werden ({exc})")


def _load_params(path: Path) -> Any:
    """Gegenstueck zu `_save_params` (gleiche Fallback-Reihenfolge)."""
    orbax_dir = path / "params"
    if orbax_dir.exists():
        try:
            import orbax.checkpoint as ocp

            checkpointer = ocp.PyTreeCheckpointer()
            return checkpointer.restore(str(orbax_dir.resolve()))
        except Exception as exc:
            print(f"[ckpt] orbax-Restore fehlgeschlagen ({exc}); versuche pickle")
    pkl_path = path / "params.pkl"
    if pkl_path.exists():
        with open(pkl_path, "rb") as f:
            return pickle.load(f)
    raise FileNotFoundError(f"Keine Parameter unter {path} gefunden (weder orbax noch pickle).")


def _find_resume_source(out_dir: Path) -> Optional[Path]:
    """Bevorzugt `best/`, sonst den juengsten `ckpt_<step>/`-Ordner."""
    best = out_dir / "best"
    if best.exists():
        return best
    candidates: list[tuple[int, Path]] = []
    for p in out_dir.glob("ckpt_*"):
        try:
            step = int(p.name.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        candidates.append((step, p))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


@dataclass
class TrainingState:
    """Buendelt Fortschritts-Tracking + Checkpointing ueber die brax-Callbacks.

    brax ruft waehrend des Trainings zwei getrennte Callbacks auf: `progress_fn`
    (liefert Metriken inkl. Reward) und optional `policy_params_fn` (liefert die
    aktuellen Policy-Parameter). Da ein Checkpoint nur mit Parametern sinnvoll
    ist, der "best"-Vergleich aber den Reward braucht, wird der zuletzt gesehene
    Reward zwischengespeichert und beim naechsten Parameter-Callback fuer den
    best/-Vergleich herangezogen -- geringfuegig verzoegert, aber unabhaengig
    von der genauen brax-internen Aufrufreihenfolge.
    """

    out_dir: Path
    best_reward: float = float("-inf")
    last_reward: Optional[float] = None
    t_prev: float = field(default_factory=time.time)
    step_prev: int = 0

    def __post_init__(self) -> None:
        self.metrics_path = self.out_dir / "metrics.jsonl"

    def on_metrics(self, step: int, metrics: dict) -> None:
        now = time.time()
        dt = now - self.t_prev
        d_step = step - self.step_prev
        steps_per_sec = d_step / dt if dt > 0 and d_step > 0 else float("nan")
        self.t_prev = now
        self.step_prev = step

        reward = _extract_reward(metrics)
        if reward is not None:
            self.last_reward = reward

        record: dict[str, Any] = {"step": int(step), "wall_time": now, "steps_per_sec": steps_per_sec}
        for key, value in metrics.items():
            try:
                record[key] = float(value)
            except (TypeError, ValueError):
                pass  # nicht-skalare Metrik -- fuer die JSONL-Zeile ignorieren
        try:
            with open(self.metrics_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            print(f"[progress] konnte metrics.jsonl nicht schreiben: {exc}")

        reward_str = f"{reward:.3f}" if reward is not None else "n/a"
        print(f"[progress] step={step:>12,}  reward={reward_str:>10}  steps/s={steps_per_sec:>8.0f}")

    def on_params(self, step: int, params: Any) -> None:
        ckpt_path = self.out_dir / f"ckpt_{step}"
        _save_params(ckpt_path, params)
        print(f"[ckpt] Zwischen-Checkpoint gespeichert: {ckpt_path}")
        if self.last_reward is not None and self.last_reward > self.best_reward:
            self.best_reward = self.last_reward
            best_path = self.out_dir / "best"
            _save_params(best_path, params)
            print(f"[ckpt] neuer bester Reward {self.best_reward:.3f} -> {best_path}")


# --------------------------------------------------------------------------- #
# CLI + Hauptprogramm
# --------------------------------------------------------------------------- #

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PPO-Training (MuJoCo Playground + Brax/JAX) fuer Humanoid-Locomotion."
    )
    p.add_argument("--env", default="G1JoystickFlatTerrain",
                    help="Playground-Env-Name (registry.load), z. B. spaeter ein H2-Env")
    p.add_argument("--num-timesteps", type=int, default=100_000_000,
                    help="Gesamtzahl Trainings-Timesteps")
    p.add_argument("--num-envs", type=int, default=2048,
                    help="Anzahl paralleler Envs (8 GB VRAM auf der M4000 -> klein halten)")
    p.add_argument("--out-dir", default=None,
                    help="Ausgabeverzeichnis (Default: ~/h2_rl_runs/<env>_<seed>)")
    p.add_argument("--seed", type=int, default=0, help="Zufalls-Seed")
    p.add_argument("--smoke", action="store_true",
                    help="Schneller Rauchtest (~Minuten): num_timesteps=200000, num_envs=256")
    p.add_argument("--resume", action="store_true",
                    help="Aus vorhandenem Checkpoint (best/ bzw. juengster ckpt_*) fortsetzen")
    args = p.parse_args(argv)

    if args.smoke:
        args.num_timesteps = 200_000
        args.num_envs = 256
        print("[setup] --smoke aktiv: num_timesteps=200000, num_envs=256")

    if args.out_dir is None:
        args.out_dir = f"~/h2_rl_runs/{args.env}_{args.seed}"
    args.out_dir = os.path.expanduser(args.out_dir)
    return args


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[setup] env={args.env}  seed={args.seed}  num_envs={args.num_envs}  "
          f"num_timesteps={args.num_timesteps:,}  out_dir={out_dir}")

    env, cfg = build_env(args.env)
    ppo_params, network_factory = build_ppo_config(args.env, args.num_envs, args.num_timesteps)

    try:
        randomizer = registry.get_domain_randomizer(args.env)
    except Exception as exc:
        print(f"[setup] kein Domain-Randomizer verfuegbar ({exc}); trainiere ohne Randomization")
        randomizer = None

    state = TrainingState(out_dir=out_dir)

    def progress_fn(step: int, metrics: dict) -> None:
        state.on_metrics(step, metrics)

    def policy_params_fn(current_step: int, make_policy: Any, params: Any) -> None:
        state.on_params(current_step, params)

    train_kwargs: dict[str, Any] = dict(ppo_params)
    train_kwargs.update(
        environment=env,
        progress_fn=progress_fn,
        network_factory=network_factory,
        seed=args.seed,
    )
    if randomizer is not None:
        train_kwargs["randomization_fn"] = randomizer
        # WICHTIG: Playground-Envs besitzen kein brax-`.sys`; der Standard-brax-
        # Domain-Randomization-Wrapper crasht daher ("'Joystick' object has no
        # attribute 'sys'"). Playgrounds eigener Wrapper wendet den (auf dem
        # mjx-Modell arbeitenden) Randomizer korrekt an.
        train_kwargs["wrap_env_fn"] = wrapper.wrap_for_brax_training

    # Nur Kwargs durchreichen, die diese brax-Version tatsaechlich kennt --
    # schuetzt gegen API-Drift zwischen brax-Versionen (fehlendes/umbenanntes Kwarg
    # soll den Lauf nicht sofort abbrechen, sondern nur mit Warnung ignoriert werden).
    train_sig = inspect.signature(ppo_train.train)
    valid_names = set(train_sig.parameters)

    if "policy_params_fn" in valid_names:
        train_kwargs["policy_params_fn"] = policy_params_fn
    else:
        print("[warn] diese brax-Version kennt kein policy_params_fn -> "
              "keine periodischen Zwischen-Checkpoints, nur best-effort Endspeicherung")

    native_ckpt_dir = out_dir / "brax_native_ckpt"
    if "save_checkpoint_path" in valid_names:
        train_kwargs["save_checkpoint_path"] = str(native_ckpt_dir)

    resume_source = _find_resume_source(out_dir) if args.resume else None
    if args.resume and "restore_checkpoint_path" in valid_names and native_ckpt_dir.exists():
        # Bevorzugter Resume-Pfad: brax-eigenes orbax-Checkpointing stellt Optimizer-
        # Zustand + Schrittzaehler mit wieder her (echtes Resume, kein Warmstart).
        train_kwargs["restore_checkpoint_path"] = str(native_ckpt_dir)
        print(f"[resume] setze mit brax-nativen Checkpoints fort: {native_ckpt_dir}")
    elif args.resume and resume_source is not None:
        print(f"[resume] WARNUNG: diese brax-Version unterstuetzt kein restore_checkpoint_path "
              f"-- ein echtes Resume (Optimizer-Zustand/Schrittzaehler) ist damit nicht moeglich. "
              f"Gefundener Parameter-Stand unter {resume_source} wird NICHT automatisch als "
              f"Warmstart eingespeist (kein passendes brax-Kwarg gefunden); Training startet "
              f"bei Schritt 0 neu. Alte Checkpoints bleiben erhalten.")
    elif args.resume:
        print(f"[resume] kein vorhandener Checkpoint unter {out_dir} gefunden -> starte neu")

    dropped = sorted(set(train_kwargs) - valid_names)
    if dropped:
        print(f"[setup] ignoriere unbekannte train()-Kwargs (brax-API-Drift?): {dropped}")
    train_kwargs = {k: v for k, v in train_kwargs.items() if k in valid_names}

    # WICHTIG (nach dem Filter, damit es garantiert durchkommt): Playground-Envs
    # besitzen kein brax-`.sys`; ohne Playgrounds Wrapper crasht brax' Standard-
    # Domain-Randomization-Wrapper ("'Joystick' object has no attribute 'sys'").
    # wrap_env_fn ist Teil der ppo.train-Signatur (verifiziert) -> unbedingt setzen.
    if "wrap_env_fn" in valid_names:
        train_kwargs["wrap_env_fn"] = wrapper.wrap_for_brax_training
    else:
        print("[warn] ppo.train kennt kein wrap_env_fn -- Playground-Env evtl. inkompatibel")

    loggable = {k: v for k, v in train_kwargs.items()
                if k not in ("environment", "progress_fn", "network_factory",
                             "policy_params_fn", "randomization_fn")}
    print(f"[setup] finale PPO-Config: {loggable}")

    t0 = time.time()
    try:
        _ensure_device_put_replicated()  # brax-0.14.2/jax-0.10-Kompatibilitaet
        make_inference_fn, params, metrics = ppo_train.train(**train_kwargs)
    except TypeError as exc:
        # Haeufigste Fehlerquelle bei brax-Versionswechseln: ein Kwarg-Name hat sich
        # geaendert. Klarer Abbruch mit Kontext statt eines kryptischen Stacktrace.
        raise SystemExit(
            f"[FEHLER] ppo_train.train() lehnte die uebergebenen Argumente ab ({exc}). "
            f"Vermutlich hat sich die brax-API geaendert -- Signatur pruefen: {train_sig}"
        ) from exc
    dauer_h = (time.time() - t0) / 3600.0
    print(f"[fertig] Training abgeschlossen in {dauer_h:.2f} h, finale Metriken: {metrics}")

    final_dir = out_dir / "final"
    _save_params(final_dir, params)
    print(f"[fertig] finale Parameter gespeichert: {final_dir}")

    env_meta = {
        "env_name": args.env,
        "seed": args.seed,
        "num_envs": args.num_envs,
        "num_timesteps": args.num_timesteps,
        "observation_size": _safe(lambda: env.observation_size),
        "action_size": _safe(lambda: env.action_size),
        "cfg": _to_plain_dict(cfg) if hasattr(cfg, "to_dict") else _safe(lambda: str(cfg)),
    }
    with open(out_dir / "env_meta.json", "w", encoding="utf-8") as f:
        json.dump(env_meta, f, indent=2, default=str)
    print(f"[fertig] Env-Metadaten gespeichert: {out_dir / 'env_meta.json'}")


if __name__ == "__main__":
    main()
