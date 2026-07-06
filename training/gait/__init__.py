"""Modellbasierter (nicht lernender) Gehregler fuer den Unitree H2 im MuJoCo-Twin.

Enthaelt reine Kinematik-/Regelungscode -- Bein-IK (`leg_ik.py`), quasi-
statischer Gangplaner (`gait.py`) und deren Verknuepfung zu Gelenkwinkeln
(`walk_controller.py`). Kein maschinelles Lernen, keine GPU noetig, nur
`numpy` und `mujoco`. Lauffaehiger Runner: `training/deploy/deploy_h2_walk.py`.
"""
