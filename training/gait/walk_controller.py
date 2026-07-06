"""Verknuepft Gangplaner (`GaitPlanner`) und Bein-IK (`LegIK`) zu Gelenkwinkeln.

Wandelt die von einem `GaitPlanner` gelieferten Welt-Sollwerte (Fusspositionen,
geplante Beckenpose) pro Bein in Beckenframe-Koordinaten um und loest sie per
inverser Kinematik in die 12 Beingelenkwinkel auf (Policy-Reihenfolge: erst
links, dann rechts -- siehe `leg_ik.POLICY_LEG_JOINTS_LEFT/_RIGHT`).
"""
from __future__ import annotations

import mujoco
import numpy as np

from training.gait.gait import GaitPlanner
from training.gait.leg_ik import LegIK


def _rotz(yaw: float) -> np.ndarray:
    """Rotationsmatrix um die Hochachse (z) fuer den Winkel `yaw` [rad]."""
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0],
    ])


class WalkController:
    """Setzt den Gangplan (Weltframe) in Beingelenkwinkel um (kinematisches Gehen).

    Die vom `GaitPlanner` gelieferte Beckenpose ist eine GEPLANTE Sollgroesse,
    keine aus der Simulation gemessene Ist-Pose: Beim rein kinematischen Gehen
    bewegt sich das reale Becken indirekt, weil der geplante (planted)
    Standfuss ueber die Kinematikkette gegen den tatsaechlichen Bodenkontakt
    reagiert. Das ist das uebliche Vorgehen bei kinematischen (nicht dynamisch
    balancierten) Gehreglern und unterscheidet sich bewusst davon, die
    Beckenpose aus der Simulation zurueckzulesen.
    """

    def __init__(self, model: mujoco.MjModel, gait: GaitPlanner) -> None:
        self.model = model
        self.gait = gait
        self._ik_left = LegIK(model, "left")
        self._ik_right = LegIK(model, "right")
        self._last_q_left: np.ndarray | None = None
        self._last_q_right: np.ndarray | None = None

    def initial_pose(self) -> np.ndarray:
        """IK-Loesung fuer die Startpose (t=0) in Policy-Reihenfolge (links, rechts)."""
        return self.compute_targets(0.0, 0.0)

    def compute_targets(self, t: float, vx: float) -> np.ndarray:
        """Berechnet die 12 Soll-Beingelenkwinkel (Policy-Reihenfolge) fuer Zeitpunkt `t`.

        Args:
            t: Gangzeit [s] (monoton steigend, siehe `GaitPlanner.update`).
            vx: gewuenschte Vorwaertsgeschwindigkeit [m/s].

        Returns:
            (12,) Gelenkwinkel in Policy-Reihenfolge (erst die 6 linken, dann
            die 6 rechten Beingelenke).
        """
        tg = self.gait.update(t, vx)
        rot = _rotz(tg.pelvis_yaw)

        # Weltziel -> Beckenframe der GEPLANTEN Beckenpose umrechnen.
        p_rel_left = rot.T @ (tg.foot_left - tg.pelvis_pos)
        p_rel_right = rot.T @ (tg.foot_right - tg.pelvis_pos)

        q_left = self._ik_left.solve(p_rel_left, q_init=self._last_q_left)
        q_right = self._ik_right.solve(p_rel_right, q_init=self._last_q_right)
        self._last_q_left = q_left
        self._last_q_right = q_right

        return np.concatenate([q_left, q_right])
