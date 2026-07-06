"""Quasi-statischer Gangplaner fuer den H2 -- rein kinematisch, kein Lernverfahren.

Ein `GaitPlanner` liefert pro Zeitpunkt `t` die Soll-Fusspositionen und die
geplante Beckenpose im Weltframe (`GaitTargets`). Die eigentliche Umsetzung
in Gelenkwinkel uebernimmt `WalkController` (`walk_controller.py`) per
inverser Kinematik pro Bein (`leg_ik.py`).

Konvention: x = vorwaerts, y = links, z = oben; der Boden ist eben.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class GaitParams:
    """Tunebare Parameter des quasi-statischen Gangs."""

    pelvis_height: float = 0.90   # nominale Beckenstandhoehe [m] (0.90 empirisch
                                  # stabiler als 0.95 -- tieferer Schwerpunkt)
    foot_lateral: float = 0.11    # seitlicher Fussabstand zur Koerpermitte [m]
    step_length: float = 0.10     # Referenz-Schrittlaenge pro Halbzyklus [m]
    step_height: float = 0.05     # Schwungfuss-Anhebung [m]
    cycle_time: float = 2.0       # Dauer eines vollen Doppelschritts [s]
    ds_ratio: float = 0.2         # Anteil Doppelstand je Halbzyklus [0..1)
    com_shift: float = 0.8        # seitl. Beckenverlagerung als Anteil von foot_lateral
                                  # (1.0 = Becken exakt ueber Standfuss; >1 moeglich)
    foot_x_offset: float = 0.04   # Fuesse um diesen Betrag VOR das Becken setzen [m].
                                  # Ohne Versatz liegt der Gesamt-CoM (mit Oberkoerper)
                                  # ~0.1 m VOR dem Knoechel -> Stand kippt nach vorn.
                                  # Der Versatz rueckt die Knoechel unter den CoM.

    def __post_init__(self) -> None:
        if self.cycle_time <= 0.0:
            raise ValueError("cycle_time muss > 0 sein")
        if not (0.0 <= self.ds_ratio < 1.0):
            raise ValueError("ds_ratio muss in [0, 1) liegen")
        if self.foot_lateral < 0.0:
            raise ValueError("foot_lateral darf nicht negativ sein")


@dataclass
class GaitTargets:
    """Sollwerte eines Gangplaners fuer einen Zeitpunkt `t` (Weltframe)."""

    pelvis_pos: np.ndarray   # (3,) Beckenposition
    pelvis_yaw: float        # Beckendrehung um die Hochachse [rad]
    foot_left: np.ndarray    # (3,) Sohlen-Sollposition links
    foot_right: np.ndarray   # (3,) Sohlen-Sollposition rechts
    swing: str                # 'left' | 'right' | 'none' -- aktuell fuehrendes Schwungbein


class GaitPlanner(ABC):
    """Abstrakte Basis fuer Gangplaner.

    Trennt die Gangplanung (hier: quasi-statisch/rein kinematisch) von der
    Umsetzung in Gelenkwinkel (`WalkController`). Ein spaeterer dynamischer
    Regler (z. B. ZMP-/Capture-Point-basiert) kann als weitere Implementierung
    dieser Basis eingehaengt werden, ohne `WalkController` aendern zu muessen.
    """

    @abstractmethod
    def reset(self) -> None:
        """Setzt internen Zustand des Planers zurueck."""

    @abstractmethod
    def update(self, t: float, vx: float) -> GaitTargets:
        """Berechnet die Sollwerte fuer Zeitpunkt `t` bei Vorwaertsgeschwindigkeit `vx`."""


def _cos_ease(x: float) -> float:
    """Glatte 0->1-Rampe (Cosinus-Ease) fuer x in [0, 1]."""
    x = min(max(x, 0.0), 1.0)
    return 0.5 * (1.0 - math.cos(math.pi * x))


class QuasiStaticGait(GaitPlanner):
    """Quasi-statischer Gang: Doppelstand-Gewichtsverlagerung + Schwungbein-Bogen.

    Ablauf je Halbzyklus (Dauer `cycle_time/2`, Anteil `ds_ratio` davon Doppelstand):

    1. Doppelstand-Phase (Beginn des Halbzyklus): Beide Fuesse stehen, das
       Becken verlagert sich seitlich glatt (Cosinus-Rampe) von der vorherigen
       Position auf `foot_lateral * 0.8` ueber dem kommenden Standfuss. Der
       Schwungfuss bewegt sich in dieser Phase noch nicht.
    2. Einzelstand-/Schwungphase (Rest des Halbzyklus): Das Becken bleibt
       seitlich ueber dem Standfuss (Schwerpunkt bleibt ueber der
       Stuetzflaeche), waehrend der Schwungfuss einen halben Sinus-Bogen
       (Anheben um `step_height`, Vorwaertsbewegung um `step_length`) beschreibt
       und wieder aufsetzt.

    Der naechste Halbzyklus beginnt mit den vertauschten Rollen (Stand-/
    Schwungbein); die dortige Doppelstand-Rampe fuehrt das Becken dabei glatt
    ueber die Mitte hinweg zur anderen Seite -- ein separater Rueckweg-Schritt
    ist dafuer nicht noetig.

    Die Fuesse selbst bleiben seitlich stets bei `y = ±foot_lateral`; nur das
    Becken pendelt seitlich. `pelvis_yaw` ist konstant 0 (geradeaus).
    """

    def __init__(self, params: GaitParams | None = None) -> None:
        self.params = params or GaitParams()
        self.reset()

    def reset(self) -> None:
        """Kein interner Zustand noetig -- Sollwerte werden rein aus `t` berechnet."""

    def _effective_step_length(self, vx: float) -> float:
        """Skaliert `step_length` linear mit `vx`, bezogen auf die Referenzgeschwindigkeit.

        `step_length`/`cycle_time` legen gemeinsam eine Referenzgeschwindigkeit
        `v_ref = step_length / (cycle_time/2)` fest. Die tatsaechliche
        Schrittlaenge wird so skaliert, dass bei konstantem `vx` die mittlere
        Gehgeschwindigkeit `vx` erreicht wird; bei `vx=0` wird auf der Stelle
        getreten (Schrittlaenge 0).
        """
        half = self.params.cycle_time / 2.0
        v_ref = self.params.step_length / half
        if v_ref == 0.0:
            return 0.0
        return self.params.step_length * (vx / v_ref)

    def update(self, t: float, vx: float) -> GaitTargets:
        p = self.params
        half = p.cycle_time / 2.0
        idx = int(t // half)          # Index des aktuellen Halbzyklus
        phase = (t - idx * half) / half  # Phase 0..1 innerhalb des Halbzyklus

        step_length = self._effective_step_length(vx)

        # Halbzyklus-Paritaet: 0 -> rechts steht, links schwingt; danach alternierend.
        swing_side = "left" if idx % 2 == 0 else "right"
        stance_side = "right" if swing_side == "left" else "left"
        stance_sign = 1.0 if stance_side == "left" else -1.0

        # Fuss-x-Fortschritt (siehe Klassen-Docstring fuer die Herleitung):
        # der Standfuss wurde am Ende des vorigen Halbzyklus dort abgesetzt,
        # der Schwungfuss startet von seiner eigenen letzten Landeposition
        # (ein voller Zyklus zuvor) und landet einen Schritt vor dem Standfuss.
        stance_x = idx * step_length
        swing_x_start = max(idx - 1, 0) * step_length
        swing_x_end = (idx + 1) * step_length

        # Doppelstand-/Schwung-Unterphasen innerhalb des Halbzyklus.
        if phase < p.ds_ratio:
            ds_progress = phase / p.ds_ratio if p.ds_ratio > 0.0 else 1.0
            swing_progress = 0.0
        else:
            ds_progress = 1.0
            denom = 1.0 - p.ds_ratio
            swing_progress = (phase - p.ds_ratio) / denom if denom > 0.0 else 1.0

        # Seitliche Beckenverlagerung: von der vorherigen Standseite (bzw. der
        # Mitte beim allerersten Halbzyklus) glatt zur aktuellen Standseite.
        prev_sign = -stance_sign if idx > 0 else 0.0
        target_y = stance_sign * p.foot_lateral * p.com_shift
        prev_y = prev_sign * p.foot_lateral * p.com_shift
        pelvis_y = prev_y + (target_y - prev_y) * _cos_ease(ds_progress)

        # Schwungfuss: halber Sinus-Bogen in z, linear (per Cosinus-Ease
        # geglaettet) in x zwischen Start- und Landeposition.
        swing_x = swing_x_start + (swing_x_end - swing_x_start) * _cos_ease(swing_progress)
        swing_z = p.step_height * math.sin(math.pi * min(max(swing_progress, 0.0), 1.0))

        if swing_side == "left":
            foot_left = np.array([swing_x, p.foot_lateral, swing_z])
            foot_right = np.array([stance_x, -p.foot_lateral, 0.0])
        else:
            foot_right = np.array([swing_x, -p.foot_lateral, swing_z])
            foot_left = np.array([stance_x, p.foot_lateral, 0.0])

        pelvis_pos = np.array([
            0.5 * (foot_left[0] + foot_right[0]),
            pelvis_y,
            p.pelvis_height,
        ])

        # Fuesse um foot_x_offset VOR das Becken setzen (Knoechel unter den CoM),
        # OHNE das Becken mitzuziehen -- pelvis_pos wurde bereits ohne Versatz aus
        # den Schrittpositionen bestimmt.
        foot_left[0] += p.foot_x_offset
        foot_right[0] += p.foot_x_offset

        return GaitTargets(
            pelvis_pos=pelvis_pos,
            pelvis_yaw=0.0,
            foot_left=foot_left,
            foot_right=foot_right,
            swing=swing_side,
        )
