"""Balance-Regler fuer den H2 -- Rueckkopplung auf die Knoechel (Ankle-Strategie).

Empirischer Befund (im MuJoCo-Twin verifiziert): Ein rein positionsgeregelter
Humanoid ist ein INSTABILES Gleichgewicht. Selbst bei perfekter Standpose (CoM
ueber der Stuetzflaeche, Fuesse flach) kippt der H2 ohne Rueckkopplung nach
wenigen Sekunden -- jede kleine Neigung waechst selbstverstaerkend. Steifere
Gelenke verschlimmern das sogar (dynamische Instabilitaet, kein Kraftmangel).

Dieser Regler fuehrt daher die Knoechel-Sollwinkel anhand der gemessenen
Becken-/Rumpfneigung nach (klassische "Ankle-Strategie"): kippt der Roboter nach
vorn, stellt der Knoechel dagegen. Das ist die einfachste geschlossene
Regelschleife und rein CPU-basiert.

WICHTIG -- Grenzen: Die Ankle-Strategie allein stabilisiert den H2 nur begrenzt
(Groessenordnung wenige Sekunden laenger, kein Dauerstand). Fuer robustes Stehen
und Gehen ist ein Ganzkoerper-Balanceregler noetig (LIPM/Capture-Point +
Schrittanpassung bzw. Whole-Body-QP) -- oder eine gelernte Policy (RL). Diese
Klasse ist bewusst als austauschbare `BalanceController`-Implementierung angelegt,
damit ein solcher Regler spaeter ohne Aenderung des uebrigen Codes eingehaengt
werden kann.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class BalanceController(ABC):
    """Abstrakte Basis eines Balance-Reglers.

    Liefert additive Korrekturen auf die Bein-Sollwinkel (12er-Vektor in
    Policy-Reihenfolge, links dann rechts) aus dem gemessenen Rumpfzustand.
    """

    @abstractmethod
    def reset(self) -> None:
        """Setzt internen Zustand zurueck."""

    @abstractmethod
    def correct(self, grav: np.ndarray, omega: np.ndarray) -> np.ndarray:
        """Additive Korrektur (12,) auf die Bein-Sollwinkel.

        Args:
            grav: projizierte Schwerkraft im Becken-Frame (3,); aufrecht ~ (0,0,-1).
            omega: Winkelgeschwindigkeit der Basis im Becken-Frame (3,).
        """


# Indizes der Knoechelgelenke im 12er-Beinvektor (Policy-Reihenfolge, siehe
# leg_ik.POLICY_LEG_JOINTS_*): links ankle_pitch=4, ankle_roll=5; rechts=10, 11.
_L_ANKLE_PITCH, _L_ANKLE_ROLL = 4, 5
_R_ANKLE_PITCH, _R_ANKLE_ROLL = 10, 11


@dataclass
class AnkleStrategyBalance(BalanceController):
    """Ankle-Strategie: Knoechel-Sollwinkel proportional zur Rumpfneigung nachfuehren.

    Kippt der Rumpf nach vorn (grav[0] > 0) bzw. zur Seite (grav[1] != 0), wird
    der jeweilige Knoechel (pitch/roll beider Beine) gegensinnig verstellt. Die
    Winkelgeschwindigkeit dient als Daempfungsterm.

    Vorzeichen und Verstaerkungen wurden im MuJoCo-Twin empirisch bestimmt
    (positives kp stabilisiert; negatives destabilisiert sofort).
    """

    kp: float = 0.7   # Proportionalanteil auf die projizierte Schwerkraft
    kd: float = 0.6   # Daempfung auf die Basis-Winkelgeschwindigkeit

    def reset(self) -> None:
        """Kein interner Zustand -- Korrektur ist rein statisch aus (grav, omega)."""

    def correct(self, grav: np.ndarray, omega: np.ndarray) -> np.ndarray:
        d_pitch = self.kp * grav[0] + self.kd * omega[1]
        d_roll = self.kp * grav[1] + self.kd * omega[0]
        out = np.zeros(12, dtype=np.float64)
        out[_L_ANKLE_PITCH] = d_pitch
        out[_R_ANKLE_PITCH] = d_pitch
        out[_L_ANKLE_ROLL] = d_roll
        out[_R_ANKLE_ROLL] = d_roll
        return out
