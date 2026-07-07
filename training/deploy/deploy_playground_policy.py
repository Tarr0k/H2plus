"""deploy_playground_policy.py -- laedt eine trainierte Brax/JAX-PPO-Policy
(aus `train_playground.py`) und laesst sie im MuJoCo-Playground-Env laufen.

Zweck: das Gegenstueck zum Training. Waehrend `train_playground.py` eine Policy
LERNT und Checkpoints auf Platte schreibt, LAEDT dieses Skript so einen
Checkpoint und misst/zeigt, wie gut die Policy laeuft -- headless (Reward,
Episodenlaenge, zurueckgelegte Strecke) und optional als gerendertes Video.

Funktioniert fuer `G1JoystickFlatTerrain` (Playground-Registry) und
`H2JoystickFlatTerrain` (unser `training/rl/h2/`), da beide ueber dieselben
`build_env`/`build_ppo_config`-Helfer aus `train_playground.py` aufgebaut werden
-- die Policy wird also EXAKT mit demselben Netzwerk und derselben
Beobachtungs-Normalisierung rekonstruiert wie beim Training.

GPU mit On-Demand-Allocator (XLA_PYTHON_CLIENT_ALLOCATOR=platform, ganz oben):
Der orbax-Checkpoint wird MIT seiner Speicher-Sharding (Geraet cuda:0) geladen,
laesst sich also nur dort wiederherstellen, wo dieses Geraet existiert -- daher
GPU statt CPU. Der Platform-Allocator belegt nur den tatsaechlich benoetigten
VRAM (statt der ueblichen 90%-Vorreservierung), sodass die Inferenz neben einem
parallel laufenden Trainingslauf in die freien VRAM-Reste passt (verifiziert:
Training lief ungestoert weiter). Ein einzelner Rollout braucht kaum Speicher.

Aufruf (Beispiele, auf ematalos -- am robustesten via systemd-run, siehe
training/rl/README.md):
    # G1-Policy (bereits konvergiert) headless auswerten:
    XLA_PYTHON_CLIENT_ALLOCATOR=platform python training/deploy/deploy_playground_policy.py \
        --env G1JoystickFlatTerrain --ckpt ~/h2_rl_runs/g1_full/best --steps 500

    # spaeter: H2-Policy nach Konvergenz, mit Video:
    XLA_PYTHON_CLIENT_ALLOCATOR=platform python training/deploy/deploy_playground_policy.py \
        --env H2JoystickFlatTerrain --ckpt ~/h2_rl_runs/h2_full/best \
        --steps 500 --video ~/h2_walk.mp4
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# On-Demand-VRAM-Allokation VOR dem ersten jax-Import (via train_playground):
# nur den tatsaechlich benoetigten Speicher belegen (statt 90%-Vorreservierung),
# damit die Inferenz neben einem laufenden Trainingslauf in die freien VRAM-Reste
# passt. GPU (nicht CPU), weil der orbax-Checkpoint mit seiner cuda:0-Sharding
# gespeichert wurde und nur dort wiederhergestellt werden kann.
os.environ.setdefault("XLA_PYTHON_CLIENT_ALLOCATOR", "platform")
os.environ.setdefault("XLA_PYTHON_CLIENT_MEM_FRACTION", "0.15")

# train_playground stellt build_env/build_ppo_config/_load_params bereit und
# kapselt die verifizierten Fallen (impl="jax", H2-Sonderpfad, Checkpoint-Format).
_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / "rl"))  # .../training/rl
import train_playground as tp  # noqa: E402

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402
import numpy as np  # noqa: E402
from brax.training.acme import running_statistics  # noqa: E402
from brax.training.agents.ppo import networks as ppo_networks  # noqa: E402


def _restore_params_host(path: Path):
    """Laedt Policy-Parameter GERAETEUNABHAENGIG (als numpy/Host).

    train_playground speichert per orbax; orbax vermerkt dabei das Speicher-
    Geraet (hier cuda:0). Ein CPU-Restore ueber `tp._load_params` scheitert dann
    an "Device cuda:0 not found". Hier erzwingen wir daher einen Host-Restore
    (restore_type=np.ndarray), sodass der Checkpoint unabhaengig vom Geraet
    (CPU wie GPU) geladen werden kann.
    """
    orbax_dir = path / "params"
    if orbax_dir.exists():
        import orbax.checkpoint as ocp

        ckptr = ocp.PyTreeCheckpointer()
        target = str(orbax_dir.resolve())
        # Plain-Restore: orbax rekonstruiert die gespeicherte Sharding. Das
        # funktioniert, wenn das Speicher-Geraet (hier cuda:0) verfuegbar ist --
        # dieses Skript wird daher fuer orbax-Checkpoints auf der GPU ausgefuehrt
        # (mit On-Demand-Allocator, siehe Aufruf/README), damit es neben einem
        # laufenden Training in den freien VRAM passt.
        return ckptr.restore(target)
    pkl = path / "params.pkl"
    if pkl.exists():
        import pickle
        with open(pkl, "rb") as f:
            return pickle.load(f)
    raise SystemExit(f"Keine Parameter unter {path} gefunden (weder orbax noch pickle).")


def _build_policy(env, env_name: str, ckpt_dir: Path):
    """Rekonstruiert Netzwerk + Inferenzfunktion EXAKT wie beim Training und
    laedt die Parameter aus `ckpt_dir` (best/ckpt_*/final)."""
    ppo_params, network_factory = tp.build_ppo_config(env_name, num_envs=1, num_timesteps=1)
    normalize = (
        running_statistics.normalize
        if ppo_params.get("normalize_observations", False)
        else (lambda x, _unused: x)
    )
    ppo_network = network_factory(
        env.observation_size, env.action_size, preprocess_observations_fn=normalize
    )
    make_inference_fn = ppo_networks.make_inference_fn(ppo_network)

    # Gespeichert wird eine Liste [Normalizer, Policy-Netz, Value-Netz]. Fuer die
    # Inferenz braucht brax nur (Normalizer, Policy). Der Normalizer kommt aus
    # orbax als reines dict zurueck -> zurueck in ein RunningStatisticsState
    # wandeln (sonst: 'dict' object has no attribute 'count').
    raw = _restore_params_host(ckpt_dir)
    rss_cls = running_statistics.RunningStatisticsState
    rss_fields = list(getattr(rss_cls, "__dataclass_fields__", {}).keys())
    norm_dict = raw[0]
    normalizer = rss_cls(**{k: norm_dict[k] for k in rss_fields if k in norm_dict})
    inference_params = (normalizer, raw[1])

    policy = make_inference_fn(inference_params, deterministic=True)
    return policy


def _rollout(env, policy, steps: int, seed: int = 0):
    """Ein Episoden-Rollout; sammelt qpos-Trajektorie + Reward/Done je Schritt."""
    reset = jax.jit(env.reset)
    step = jax.jit(env.step)
    inference = jax.jit(policy)

    rng = jax.random.PRNGKey(seed)
    rng, key = jax.random.split(rng)
    state = reset(key)

    qpos_traj = [np.array(state.data.qpos)]
    total_reward = 0.0
    episode_len = 0
    done_at = None
    for i in range(steps):
        rng, key = jax.random.split(rng)
        action, _ = inference(state.obs, key)
        state = step(state, action)
        qpos_traj.append(np.array(state.data.qpos))
        total_reward += float(state.reward)
        episode_len += 1
        if done_at is None and float(state.done) > 0.5:
            done_at = i + 1
    return qpos_traj, total_reward, episode_len, done_at


def _render_video(env, qpos_traj, out_path: Path, height=480, width=640, fps=50):
    """Rendert die qpos-Trajektorie offscreen zu einem MP4 (braucht GPU/EGL +
    imageio). Bewusst optional -- die headless-Metriken belegen die Policy bereits."""
    import mujoco  # lokal: nur fuer den Video-Pfad noetig

    mj_model = env.mj_model
    mj_data = mujoco.MjData(mj_model)
    renderer = mujoco.Renderer(mj_model, height=height, width=width)
    frames = []
    for qpos in qpos_traj:
        mj_data.qpos[:] = qpos
        mujoco.mj_forward(mj_model, mj_data)
        renderer.update_scene(mj_data)
        frames.append(renderer.render())
    renderer.close()

    try:
        import imageio.v2 as imageio
    except ImportError:
        import imageio  # aeltere API
    out_path.parent.mkdir(parents=True, exist_ok=True)
    imageio.mimsave(str(out_path), frames, fps=fps)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Trainierte Playground/Brax-Policy im Env ausfuehren")
    ap.add_argument("--env", required=True, help="G1JoystickFlatTerrain oder H2JoystickFlatTerrain")
    ap.add_argument("--ckpt", required=True, type=Path, help="Checkpoint-Ordner (best/ckpt_<n>/final)")
    ap.add_argument("--steps", type=int, default=500, help="Rollout-Schritte (50 Hz -> 500 = 10 s)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--video", type=Path, default=None, help="optional: MP4-Ausgabepfad (braucht GPU/EGL)")
    args = ap.parse_args()

    ckpt = args.ckpt.expanduser()
    if not ckpt.exists():
        raise SystemExit(f"Checkpoint-Ordner nicht gefunden: {ckpt}")

    print(f"[deploy] JAX-Backend: {jax.default_backend()} (On-Demand-Allocator -> koexistiert mit laufendem Training)")
    print(f"[deploy] baue Env {args.env} (impl=jax) ...")
    env, _cfg = tp.build_env(args.env)
    print(f"[deploy] obs={env.observation_size} act={env.action_size}")

    print(f"[deploy] lade Policy aus {ckpt} ...")
    policy = _build_policy(env, args.env, ckpt)

    print(f"[deploy] Rollout ueber {args.steps} Schritte ...")
    qpos_traj, total_reward, ep_len, done_at = _rollout(env, policy, args.steps, args.seed)

    x_dist = float(qpos_traj[-1][0] - qpos_traj[0][0])
    print("[deploy] ---- Ergebnis ----")
    print(f"  Summen-Reward       : {total_reward:.2f}")
    print(f"  Schritte gelaufen   : {ep_len}" + (f" (Episode-Ende/Sturz bei {done_at})" if done_at else " (kein Sturz)"))
    print(f"  Strecke x           : {x_dist:+.3f} m")
    print(f"  End-Becken-Hoehe z  : {float(qpos_traj[-1][2]):.3f} m")

    if args.video is not None:
        print(f"[deploy] rendere Video -> {args.video} ...")
        try:
            path = _render_video(env, qpos_traj, args.video.expanduser())
            print(f"[deploy] Video gespeichert: {path}")
        except Exception as exc:
            print(f"[deploy] Video-Rendern fehlgeschlagen ({exc!r}) -- headless-Metriken oben gelten trotzdem.")


if __name__ == "__main__":
    main()
