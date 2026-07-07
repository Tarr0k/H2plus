"""Basisklasse fuer H2-Umgebungen (analog `_g1_reference/base.py`).

Kernunterschied zu G1: JEDER Zugriff auf ein einzelnes Gelenk laeuft ueber den
Aktuator-NAMEN (siehe `h2_constants.ACTUATOR_ORDER`) -> `actuator_trnid` ->
`jnt_qposadr`/`jnt_dofadr`. G1 kann sich auf `qpos[7:]`/`qvel[6:]`-Slices
verlassen, weil dort die qpos-Baumreihenfolge zufaellig mit der Aktuator-
Reihenfolge uebereinstimmt. Bei H2 ist das NICHT der Fall (verifiziert, siehe
`training/deploy/deploy_h2_g1policy.py`: qpos-Reihenfolge ist Beine/Taille/
KOPF/ARME, Aktuator-Reihenfolge ist Beine/Taille/ARME/KOPF). Diese Klasse baut
deshalb bei der Konstruktion feste Index-Arrays (`self._qpos_adr`,
`self._qvel_adr`, beide in ACTUATOR_ORDER-Reihenfolge), die `joystick.py`
ANSTELLE jedes `[7:]`/`[6:]`-Slices verwenden muss (siehe die Hilfsmethoden
`get_actuator_qpos/-qvel/-qacc` unten).
"""

from typing import Any, Dict, Optional, Union

import mujoco
import numpy as np
from ml_collections import config_dict
from mujoco import mjx

from mujoco_playground._src import mjx_env

from . import h2_constants as consts


class H2Env(mjx_env.MjxEnv):
  """Basisklasse fuer H2-Umgebungen."""

  def __init__(
      self,
      xml_path: str,
      config: config_dict.ConfigDict,
      config_overrides: Optional[Dict[str, Union[str, int, list]]] = None,
  ) -> None:
    super().__init__(config, config_overrides)

    # Kein Asset-Bundling wie bei G1 (get_assets() aus mujoco_menagerie) noetig:
    # `build_h2_mjx_model.py` schreibt Mesh-Verweise nach dem Bauen als ABSOLUTE
    # Pfade auf ematalos -- `from_xml_path` genuegt.
    self._mj_model = mujoco.MjModel.from_xml_path(xml_path)
    self._mj_model.opt.timestep = self.sim_dt

    # --- Aktuator -> (Gelenk-ID, qpos-/qvel-Adresse), EINMALIG, namensbasiert ---
    actuator_ids = []
    for name in consts.ACTUATOR_ORDER:
      aid = mujoco.mj_name2id(self._mj_model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
      if aid < 0:
        vorhandene = [
            mujoco.mj_id2name(self._mj_model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
            for i in range(self._mj_model.nu)
        ]
        raise ValueError(
            f"Aktuator '{name}' nicht im H2-Modell ({xml_path}) gefunden. "
            f"Vorhandene Aktuatoren ({len(vorhandene)}): {vorhandene}. "
            "Vermutlich stimmt die Namenskonvention fuer Taille/Arme/Kopf in "
            "h2_constants.ACTUATOR_ORDER nicht -- bitte gegenpruefen/anpassen."
        )
      actuator_ids.append(aid)
    self._actuator_ids = np.array(actuator_ids, dtype=np.int32)
    self._joint_ids = self._mj_model.actuator_trnid[self._actuator_ids, 0]
    # qpos-/qvel-Adresse JE AKTUATOR, in ACTUATOR_ORDER-Reihenfolge. Ersetzt bei
    # H2 jedes `data.qpos[7:]`/`data.qvel[6:]`-Slicing aus der G1-Vorlage.
    self._qpos_adr = self._mj_model.jnt_qposadr[self._joint_ids]
    self._qvel_adr = self._mj_model.jnt_dofadr[self._joint_ids]

    if self._config.restricted_joint_range:
      raw_range = self._mj_model.jnt_range[self._joint_ids]
      restricted = consts.restricted_joint_range(raw_range)
      self._mj_model.jnt_range[self._joint_ids] = restricted
      # actuator_ctrlrange-Reihenfolge == Aktuator-Reihenfolge (per Definition),
      # `restricted` ist bereits in dieser Reihenfolge (via self._joint_ids).
      self._mj_model.actuator_ctrlrange[self._actuator_ids] = restricted

    self._mj_model.vis.global_.offwidth = 3840
    self._mj_model.vis.global_.offheight = 2160

    self._mjx_model = mjx.put_model(self._mj_model, impl=self._config.impl)
    self._xml_path = xml_path

  # --- Gelenk-Umsortierung: IMMER hierueber, NIE per [7:]/[6:]-Slice ----------

  def get_actuator_qpos(self, data: mjx.Data) -> Any:
    """qpos der 31 Gelenke in ACTUATOR_ORDER-Reihenfolge (Ersatz fuer `qpos[7:]`)."""
    return data.qpos[self._qpos_adr]

  def get_actuator_qvel(self, data: mjx.Data) -> Any:
    """qvel der 31 Gelenke in ACTUATOR_ORDER-Reihenfolge (Ersatz fuer `qvel[6:]`)."""
    return data.qvel[self._qvel_adr]

  def get_actuator_qacc(self, data: mjx.Data) -> Any:
    """qacc der 31 Gelenke in ACTUATOR_ORDER-Reihenfolge (Ersatz fuer `qacc[6:]`)."""
    return data.qacc[self._qvel_adr]

  # --- Sensor-Zugriffe (identisch zu G1: Sensor-NAME = f"{SENSOR}_{frame}") ---

  def get_gravity(self, data: mjx.Data, frame: str) -> Any:
    return mjx_env.get_sensor_data(self.mj_model, data, f"{consts.GRAVITY_SENSOR}_{frame}")

  def get_global_linvel(self, data: mjx.Data, frame: str) -> Any:
    return mjx_env.get_sensor_data(self.mj_model, data, f"{consts.GLOBAL_LINVEL_SENSOR}_{frame}")

  def get_global_angvel(self, data: mjx.Data, frame: str) -> Any:
    return mjx_env.get_sensor_data(self.mj_model, data, f"{consts.GLOBAL_ANGVEL_SENSOR}_{frame}")

  def get_local_linvel(self, data: mjx.Data, frame: str) -> Any:
    return mjx_env.get_sensor_data(self.mj_model, data, f"{consts.LOCAL_LINVEL_SENSOR}_{frame}")

  def get_accelerometer(self, data: mjx.Data, frame: str) -> Any:
    return mjx_env.get_sensor_data(self.mj_model, data, f"{consts.ACCELEROMETER_SENSOR}_{frame}")

  def get_gyro(self, data: mjx.Data, frame: str) -> Any:
    return mjx_env.get_sensor_data(self.mj_model, data, f"{consts.GYRO_SENSOR}_{frame}")

  # --- Accessors (identisch zu G1) --------------------------------------------

  @property
  def xml_path(self) -> str:
    return self._xml_path

  @property
  def action_size(self) -> int:
    return self._mjx_model.nu

  @property
  def mj_model(self) -> mujoco.MjModel:
    return self._mj_model

  @property
  def mjx_model(self) -> mjx.Model:
    return self._mjx_model
