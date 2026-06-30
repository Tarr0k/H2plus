"""Policy-Paket: austauschbare Manipulations-Policies für den H2-Lader.

Dieses Paket implementiert ADR-0007 (GR00T-Policy-Backend-Zielarchitektur):
ein abstraktes ``PolicyInterface`` mit konkreten Backends sowie
Sicherheits- und Fallback-Wrapper.

Verfügbare Klassen:
    - ``PolicyInterface``:  Abstrakte Basis (ABC).
    - ``Observation``:      Eingabe an ``predict()``.
    - ``Action``:           Ausgabe von ``predict()``.
    - ``ScriptedPolicy``:   Teach-&-Replay als Policy (deterministisch).
    - ``GrootPolicy``:      GR00T N1.7-Stub (Zielzustand, noch nicht implementiert).
    - ``SafeguardedPolicy``:Gelenk-Clamping-Wrapper für beliebige Inner-Policy.
    - ``FallbackPolicy``:   Wechselt bei Exception zum Fallback-Backend.
"""

from .base import Action, Observation, PolicyInterface
from .fallback import FallbackPolicy
from .groot_policy import GrootPolicy
from .safeguard import SafeguardedPolicy
from .scripted_policy import ScriptedPolicy

__all__ = [
    "Action",
    "FallbackPolicy",
    "GrootPolicy",
    "Observation",
    "PolicyInterface",
    "SafeguardedPolicy",
    "ScriptedPolicy",
]
