"""Inverse Kinematik fuer ein einzelnes H2-Bein (6 DoF), Becken als Basis.

Loest per Damped-Least-Squares (DLS) gegen MuJoCos eigene Jacobi-Matrix
(`mj_jac`), gegen eine INTERNE Scratch-`MjData`-Instanz -- die laufende
Simulation wird dabei niemals beruehrt.
"""
from __future__ import annotations

import mujoco
import numpy as np

# Policy-Reihenfolge der Beingelenke je Seite (hip_pitch, hip_roll, hip_yaw,
# knee, ankle_pitch, ankle_roll). Diese Namen sind die H2-AKTUATOR-Namen; das
# namensbasierte Mapping (mj_name2id + actuator_trnid) loest damit automatisch
# den H2-internen Knoechel-Tausch (real ankle_roll, ankle_pitch) auf, siehe
# `training/deploy/deploy_h2_g1policy.py` bzw. `training/h2_joint_map.md`.
POLICY_LEG_JOINTS_LEFT: list[str] = [
    "left_hip_pitch", "left_hip_roll", "left_hip_yaw", "left_knee",
    "left_ankle_pitch", "left_ankle_roll",
]
POLICY_LEG_JOINTS_RIGHT: list[str] = [
    "right_hip_pitch", "right_hip_roll", "right_hip_yaw", "right_knee",
    "right_ankle_pitch", "right_ankle_roll",
]

# Sohlen-Mittelpunkt im Fuss-Koerper-Frame (verifiziert am H2-Modell, in Metern).
_SOLE_OFFSET: dict[str, np.ndarray] = {
    "left": np.array([0.035, 0.036, -0.04], dtype=np.float64),
    "right": np.array([0.035, -0.036, -0.04], dtype=np.float64),
}

# Neutrale Fussorientierung im Beckenframe (wxyz) -- Fuss flach/ausgerichtet.
_IDENTITY_QUAT = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

# Nominale Bein-Startpose (leichte Kniebeuge, Policy-Reihenfolge). Wird als
# Default-Startschaetzung fuer die IK verwendet. WICHTIG: von der gestreckten
# Nullstellung (q=0) aus divergiert die DLS-IK in die Gelenkanschlaege (Knie-
# Singularitaet); aus dieser Kniebeuge konvergiert sie dagegen in 2-4 Schritten.
_NOMINAL_LEG_POSE = np.array([-0.3, 0.0, 0.0, 0.6, -0.3, 0.0], dtype=np.float64)


def _actuator_id(model: mujoco.MjModel, name: str) -> int:
    """Aktuator-ID per Name, mit klarer Fehlermeldung statt stillem -1."""
    aid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
    if aid < 0:
        raise ValueError(f"Aktuator '{name}' nicht im Modell gefunden")
    return aid


class LegIK:
    """Damped-Least-Squares-IK fuer ein H2-Bein (6 DoF) relativ zum Becken.

    Arbeitet gegen eine eigene, interne `MjData`-Instanz ("Scratch"). Darin
    wird das Becken (Free-Joint) am Ursprung fixiert und aufrecht gehalten,
    sodass Welt- und Beckenframe der Scratch-Instanz identisch sind -- die
    IK loest also direkt im Beckenframe, ohne die eigentliche Simulation
    anzufassen.
    """

    def __init__(self, model: mujoco.MjModel, side: str) -> None:
        if side not in ("left", "right"):
            raise ValueError(f"side muss 'left' oder 'right' sein, nicht {side!r}")
        self.side = side
        self.model = model
        self._data = mujoco.MjData(model)  # Scratch-MjData, unabhaengig von der Sim

        joint_names = POLICY_LEG_JOINTS_LEFT if side == "left" else POLICY_LEG_JOINTS_RIGHT
        act_ids = np.array([_actuator_id(model, n) for n in joint_names], dtype=int)
        jnt_ids = model.actuator_trnid[act_ids, 0]
        self._qadr = model.jnt_qposadr[jnt_ids]  # qpos-Adressen der 6 Beingelenke
        self._vadr = model.jnt_dofadr[jnt_ids]   # dof/qvel-Adressen der 6 Beingelenke

        # Gelenkgrenzen fuer das Clipping; nur dort anwenden, wo das Gelenk
        # tatsaechlich als "limited" markiert ist (sonst waere jnt_range=[0,0]
        # faelschlich eine Nullbegrenzung).
        limited = model.jnt_limited[jnt_ids].astype(bool)
        rng = model.jnt_range[jnt_ids]
        self._q_min = np.where(limited, rng[:, 0], -np.inf)
        self._q_max = np.where(limited, rng[:, 1], np.inf)

        foot_body = f"{side}_ankle_pitch_link"
        self._foot_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, foot_body)
        if self._foot_bid < 0:
            raise ValueError(f"Fuss-Koerper '{foot_body}' nicht im Modell gefunden")
        self._sole_offset = _SOLE_OFFSET[side]

    def _reset_scratch(self, q: np.ndarray) -> None:
        """Scratch-Becken auf Ursprung/aufrecht fixieren, Beinwinkel q setzen."""
        d = self._data
        d.qpos[:] = 0.0
        d.qpos[3] = 1.0  # Quaternion wxyz = Identitaet (Becken aufrecht, kein Versatz)
        d.qpos[self._qadr] = q
        d.qvel[:] = 0.0

    def _foot_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """Aktuelle Sohlenposition und Fussorientierung (Welt- == Beckenframe)."""
        d = self._data
        rot = d.xmat[self._foot_bid].reshape(3, 3)
        pos = d.xpos[self._foot_bid] + rot @ self._sole_offset
        quat = np.zeros(4, dtype=np.float64)
        mujoco.mju_mat2Quat(quat, d.xmat[self._foot_bid])
        return pos, quat

    def solve(
        self,
        target_pos: np.ndarray,
        target_quat: np.ndarray | None = None,
        q_init: np.ndarray | None = None,
        iters: int = 40,
        damping: float = 1e-2,
        tol: float = 1e-4,
        dq_clip: float = 0.2,
    ) -> np.ndarray:
        """Loest die inverse Kinematik des Beins per Damped-Least-Squares.

        Args:
            target_pos: gewuenschte Sohlenposition im Beckenframe (3,).
            target_quat: gewuenschte Fussorientierung im Beckenframe (wxyz,
                4,). Ohne Angabe wird der Fuss flach/ausgerichtet erwartet
                (Identitaetsquaternion).
            q_init: Startschaetzung der 6 Beinwinkel (Policy-Reihenfolge
                dieser Seite). Ohne Angabe wird von der Nullstellung
                gestartet.
            iters: maximale Anzahl DLS-Iterationen.
            damping: DLS-Daempfung (Levenberg-Marquardt-Term).
            tol: Abbruchschwelle fuer die Norm des 6D-Fehlervektors.
            dq_clip: Maximale Schrittweite (Norm) pro Iteration [rad]. Begrenzt
                den DLS-Schritt, damit die IH aus schlechten Startlagen nicht in
                die Gelenkanschlaege ueberschiesst.

        Returns:
            Die 6 geloesten Beinwinkel (Policy-Reihenfolge dieser Seite),
            auf die Gelenkgrenzen geclippt.
        """
        m, d = self.model, self._data
        if target_quat is None:
            target_quat = _IDENTITY_QUAT
        target_pos = np.asarray(target_pos, dtype=np.float64)
        target_quat = np.asarray(target_quat, dtype=np.float64)
        q = _NOMINAL_LEG_POSE.copy() if q_init is None else np.array(q_init, dtype=np.float64)

        jacp = np.zeros((3, m.nv))
        jacr = np.zeros((3, m.nv))

        for _ in range(iters):
            self._reset_scratch(q)
            mujoco.mj_kinematics(m, d)
            mujoco.mj_comPos(m, d)  # fuellt d.cdof -- ohne das liefert mj_jac eine Nullmatrix
            cur_pos, cur_quat = self._foot_pose()

            e_pos = target_pos - cur_pos
            e_rot = np.zeros(3, dtype=np.float64)
            mujoco.mju_subQuat(e_rot, target_quat, cur_quat)
            # mju_subQuat liefert den Fehler im LOKALEN Fuss-Frame; mj_jac (jacr)
            # arbeitet im WELT-Frame -> Fehler in den Weltframe drehen, sonst
            # divergiert die kombinierte Positions-/Orientierungs-IK.
            e_rot = d.xmat[self._foot_bid].reshape(3, 3) @ e_rot
            e = np.concatenate([e_pos, e_rot])

            if np.linalg.norm(e) < tol:
                break

            mujoco.mj_jac(m, d, jacp, jacr, cur_pos, self._foot_bid)
            jac = np.vstack([jacp[:, self._vadr], jacr[:, self._vadr]])  # (6, 6)

            jjt = jac @ jac.T + (damping ** 2) * np.eye(6)
            try:
                dq = jac.T @ np.linalg.solve(jjt, e)
            except np.linalg.LinAlgError:
                dq = jac.T @ np.linalg.lstsq(jjt, e, rcond=None)[0]

            # Schrittweite begrenzen (Anti-Ueberschwingen in die Anschlaege).
            dq_norm = np.linalg.norm(dq)
            if dq_norm > dq_clip:
                dq = dq * (dq_clip / dq_norm)

            q = np.clip(q + dq, self._q_min, self._q_max)

        return q
