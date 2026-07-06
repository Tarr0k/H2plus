"""RL-Trainingscode fuer Humanoid-Locomotion (MuJoCo Playground + Brax PPO auf JAX/GPU).

Enthaelt das eigentliche Trainingsskript (`train_playground.py`), das auf einem
separaten Linux+GPU-Rechner ausgefuehrt wird -- nicht auf dem Windows-
Entwicklungsrechner (siehe `training/README.md`). Ergaenzt `training/gait/`
(modellbasierter, nicht lernender Gehregler) um den lernenden Trainingspfad.
"""
