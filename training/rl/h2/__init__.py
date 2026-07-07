"""H2-MJX-Trainingsumgebung (Joystick-Task, flaches Terrain).

Adaptiert aus der Playground-G1-Vorlage (`training/rl/_g1_reference/`) fuer den
Unitree H2. Siehe `README.md` in diesem Verzeichnis fuer:
  - den Build-Schritt (`build_h2_mjx_model.py`, muss VOR dem ersten Training
    einmalig auf ematalos laufen),
  - die direkte Instanziierung (kein Registry-Eintrag, siehe unten),
  - offene Punkte, die gegen das echte H2-Modell verifiziert werden muessen.

Direkte Instanziierung (kein `mujoco_playground.registry.load`, da H2 kein
Playground-Erstanbieter-Env ist):

    from h2 import H2JoystickFlatTerrain, default_config

    cfg = default_config()
    cfg.impl = "jax"  # auf der Ziel-GPU (M4000) zwingend, siehe train_playground.py
    env = H2JoystickFlatTerrain(config=cfg)
"""

from . import h2_constants
from .joystick import H2JoystickFlatTerrain, default_config
from .randomize import bind as bind_domain_randomize
from .randomize import domain_randomize

__all__ = [
    "H2JoystickFlatTerrain",
    "default_config",
    "domain_randomize",
    "bind_domain_randomize",
    "h2_constants",
]
