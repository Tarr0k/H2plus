#!/usr/bin/env bash
# patch_unitree_mujoco_h2.sh -- macht Unitrees MuJoCo-DDS-Bridge H2-tauglich.
#
# Problem: unitree_mujoco/simulate_python/unitree_sdk2py_bridge.py waehlt das
# DDS-IDL beim Import per `if config.ROBOT=="g1":` (-> unitree_hg, 35 Motoren),
# sonst unitree_go (20 Motoren). H2 (config.ROBOT="h2") faellt in den else-Zweig
# und bekommt das 20-Motoren-go-IDL; da H2 aber 31 Aktuatoren hat, wirft der
# LowState-Publish-Thread bei motor_state[i], i>=20, laufend `IndexError`.
#
# Fix: alle Unitree-Humanoiden (g1/h1/h2) nutzen das unitree_hg-IDL (bis 35
# Motoren). Ein Einzeiler; Original wird als *.orig gesichert. Idempotent.
#
# Verifiziert am 2026-07-07 auf ematalos: nach dem Patch startet die Bridge mit
# config.ROBOT="h2" ohne IndexError (0 statt Dauerschleife), gibt die H2-Szene
# aus und publiziert rt/lowstate mit 31 Motoren.
#
# Aufruf:  bash patch_unitree_mujoco_h2.sh [PFAD_ZU_unitree_mujoco]
set -euo pipefail

REPO="${1:-$HOME/unitree_mujoco}"
BRIDGE="$REPO/simulate_python/unitree_sdk2py_bridge.py"

[ -f "$BRIDGE" ] || { echo "FEHLER: $BRIDGE nicht gefunden"; exit 1; }

if grep -q 'config.ROBOT in ("g1","h1","h2")' "$BRIDGE"; then
  echo "Bereits gepatcht: $BRIDGE"
  exit 0
fi

[ -f "$BRIDGE.orig" ] || cp "$BRIDGE" "$BRIDGE.orig"
sed -i 's/if config.ROBOT=="g1":/if config.ROBOT in ("g1","h1","h2"):/' "$BRIDGE"

if grep -q 'config.ROBOT in ("g1","h1","h2")' "$BRIDGE"; then
  echo "OK gepatcht (Backup: $BRIDGE.orig):"
  grep -n 'config.ROBOT in' "$BRIDGE"
else
  echo "FEHLER: Patch nicht angewendet -- Zeile 'if config.ROBOT==\"g1\":' nicht gefunden?"
  exit 1
fi
