"""Domain-Randomization fuer H2 (adaptiert aus `_g1_reference/randomize.py`).

Zwei Abweichungen von der G1-Vorlage, beide um "erfundene Zahlen" zu vermeiden:

  - `TORSO_BODY_ID` ist bei G1 ein hartkodierter Modul-Konstante (16), weil dort
    die Body-Reihenfolge im XML bekannt/stabil ist. Fuer H2 wissen wir das nicht
    und wollen es nicht raten -- `domain_randomize` nimmt `torso_body_id` deshalb
    als Parameter entgegen. Der Aufrufer (siehe `train_playground.py`) ermittelt
    ihn zur Laufzeit aus dem echten Modell: `env.mj_model.body(ROOT_BODY).id`
    und bindet ihn per `functools.partial`, BEVOR die Funktion als
    `randomization_fn` an `ppo.train()` uebergeben wird (die Playground-
    Wrapper-Signatur erlaubt nur `(model, rng)`).
  - Die Gelenkanzahl (29 bei G1) wird nicht hartkodiert, sondern aus
    `model.nv - 6` abgeleitet (6 Freiheitsgrade des Floating-Base-Gelenks).
"""

import functools
from typing import Optional

import jax
from mujoco import mjx


def domain_randomize(model: mjx.Model, rng: jax.Array, torso_body_id: Optional[int] = None):
  if torso_body_id is None:
    raise ValueError(
        "domain_randomize() braucht `torso_body_id` (siehe Modul-Docstring) -- "
        "vor der Uebergabe an ppo.train() per functools.partial binden, z. B.: "
        "functools.partial(domain_randomize, torso_body_id=env.mj_model.body("
        "h2_constants.ROOT_BODY).id)"
    )
  n_actuated_dofs = model.nv - 6  # Freeejoint hat 6 DoF, Rest sind die H2-Gelenke.

  @jax.vmap
  def rand_dynamics(rng):
    # Boden-/Fuss-Reibung: =U(0.4, 1.0). (Wert 1:1 aus G1-Vorlage uebernommen.)
    rng, key = jax.random.split(rng)
    friction = jax.random.uniform(key, minval=0.4, maxval=1.0)
    pair_friction = model.pair_friction.at[0:2, 0:2].set(friction)

    # Reibung skalieren: *U(0.5, 2.0).
    rng, key = jax.random.split(rng)
    frictionloss = model.dof_frictionloss[6:] * jax.random.uniform(
        key, shape=(n_actuated_dofs,), minval=0.5, maxval=2.0
    )
    dof_frictionloss = model.dof_frictionloss.at[6:].set(frictionloss)

    # Armatur skalieren: *U(1.0, 1.05).
    rng, key = jax.random.split(rng)
    armature = model.dof_armature[6:] * jax.random.uniform(
        key, shape=(n_actuated_dofs,), minval=1.0, maxval=1.05
    )
    dof_armature = model.dof_armature.at[6:].set(armature)

    # Alle Koerpermassen skalieren: *U(0.9, 1.1).
    rng, key = jax.random.split(rng)
    dmass = jax.random.uniform(key, shape=(model.nbody,), minval=0.9, maxval=1.1)
    body_mass = model.body_mass.at[:].set(model.body_mass * dmass)

    # Zusatzmasse am Torso: +U(-1.0, 1.0).
    rng, key = jax.random.split(rng)
    dmass = jax.random.uniform(key, minval=-1.0, maxval=1.0)
    body_mass = body_mass.at[torso_body_id].set(body_mass[torso_body_id] + dmass)

    # qpos0 jittern: +U(-0.05, 0.05).
    rng, key = jax.random.split(rng)
    qpos0 = model.qpos0
    qpos0 = qpos0.at[7:].set(
        qpos0[7:] + jax.random.uniform(key, shape=(n_actuated_dofs,), minval=-0.05, maxval=0.05)
    )

    return pair_friction, dof_frictionloss, dof_armature, body_mass, qpos0

  (
      pair_friction,
      frictionloss,
      armature,
      body_mass,
      qpos0,
  ) = rand_dynamics(rng)

  in_axes = jax.tree_util.tree_map(lambda x: None, model)
  in_axes = in_axes.tree_replace({
      "pair_friction": 0,
      "dof_frictionloss": 0,
      "dof_armature": 0,
      "body_mass": 0,
      "qpos0": 0,
  })

  model = model.tree_replace({
      "pair_friction": pair_friction,
      "dof_frictionloss": frictionloss,
      "dof_armature": armature,
      "body_mass": body_mass,
      "qpos0": qpos0,
  })

  return model, in_axes


def bind(torso_body_id: int):
  """Komfort-Helfer: `functools.partial(domain_randomize, torso_body_id=...)`."""
  return functools.partial(domain_randomize, torso_body_id=torso_body_id)
