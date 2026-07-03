#!/usr/bin/env bash
# =============================================================================
# H2plus — Setup unitree_mujoco Digital-Twin auf Ubuntu (idempotent)
# =============================================================================
# Installiert den kompletten Stack, um den H2 in der MuJoCo-Physiksimulation
# (unitree_mujoco) zu fahren und den h2_loader-Bring-up dagegen laufen zu lassen:
#   apt-Deps -> CycloneDDS 0.10.2 -> unitree_sdk2 (C++) -> unitree_sdk2_python
#   -> MuJoCo-Release -> unitree_mujoco (C++-Sim) -> h2plus-Repo (venv, Tests)
#
# CPU-Physik — KEINE NVIDIA/RTX-GPU nötig (die braucht nur Isaac Sim / GR00T).
# Nur Ubuntu 20.04/22.04 (Linux). Der MuJoCo-Viewer ist eine GUI (Display nötig);
# die DDS-Bridge und der headless-Bring-up (Phase 1) laufen auch ohne Fenster.
#
# ⚠️ HARDWARE-/ZIELSYSTEM-UNGETESTET: an den offiziellen READMEs orientiert
#    (unitree_sdk2, unitree_sdk2_python, unitree_mujoco). Am ersten Reallauf auf
#    dem Ziel-Ubuntu verifizieren. Verändert das System (apt, /opt, ~/.mujoco).
#
# Nutzung:
#   bash scripts/setup_ubuntu_twin.sh --yes
# Konfiguration per Umgebungsvariablen (Defaults in Klammern):
#   MUJOCO_VERSION (3.3.6) | WORKDIR (~/h2_twin) | SDK2_PREFIX (/opt/unitree_robotics)
#   CYCLONEDDS_DIR (~/cyclonedds) | H2PLUS_REPO (https://github.com/Tarr0k/H2plus.git)
# =============================================================================
set -euo pipefail

MUJOCO_VERSION="${MUJOCO_VERSION:-3.3.6}"
WORKDIR="${WORKDIR:-$HOME/h2_twin}"
SDK2_PREFIX="${SDK2_PREFIX:-/opt/unitree_robotics}"
CYCLONEDDS_DIR="${CYCLONEDDS_DIR:-$HOME/cyclonedds}"
H2PLUS_REPO="${H2PLUS_REPO:-https://github.com/Tarr0k/H2plus.git}"
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unbekanntes Argument: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[0;32mOK:\033[0m %s\n' "$*"; }
warn() { printf '   \033[0;33mWARN:\033[0m %s\n' "$*"; }
die()  { printf '\n\033[0;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }

# --- sudo-Helfer (non-interaktiv; verlangt NOPASSWD oder aktives sudo-Ticket) --
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo -n"
  $SUDO true 2>/dev/null || die "sudo ist nicht ohne Passwort nutzbar. Bitte NOPASSWD einrichten \
oder das Skript als root ausführen. (Nicht-interaktiver Lauf kann kein Passwort abfragen.)"
fi

# --- Vorbedingungen -----------------------------------------------------------
log "Vorbedingungen prüfen"
[ -r /etc/os-release ] && . /etc/os-release || die "/etc/os-release fehlt — ist das Ubuntu?"
case "${ID:-}${ID_LIKE:-}" in *ubuntu*|*debian*) ok "OS: ${PRETTY_NAME:-unbekannt}" ;; *) warn "Kein Ubuntu/Debian erkannt (${PRETTY_NAME:-?}) — fahre trotzdem fort" ;; esac
command -v git >/dev/null || true

if [ "$ASSUME_YES" -ne 1 ]; then
  echo
  echo "Dieses Skript installiert Pakete (apt), baut CycloneDDS/unitree_sdk2/unitree_mujoco"
  echo "und legt Dateien unter $WORKDIR, $CYCLONEDDS_DIR, ~/.mujoco und $SDK2_PREFIX an."
  read -r -p "Fortfahren? [y/N] " ans
  case "$ans" in y|Y|j|J) ;; *) die "Abgebrochen." ;; esac
fi

mkdir -p "$WORKDIR"

# --- 1. apt-Abhängigkeiten ----------------------------------------------------
log "1/7  apt-Abhängigkeiten installieren"
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get update -y
$SUDO apt-get install -y \
  build-essential cmake git wget curl pkg-config \
  python3 python3-pip python3-venv \
  libyaml-cpp-dev libspdlog-dev libboost-all-dev libglfw3-dev libeigen3-dev
ok "System-Pakete installiert"

# --- 2. CycloneDDS 0.10.2 -----------------------------------------------------
log "2/7  CycloneDDS 0.10.x bauen/installieren"
if [ -d "$CYCLONEDDS_DIR/install" ]; then
  ok "CycloneDDS bereits vorhanden ($CYCLONEDDS_DIR/install)"
else
  [ -d "$CYCLONEDDS_DIR" ] || git clone https://github.com/eclipse-cyclonedds/cyclonedds -b releases/0.10.x "$CYCLONEDDS_DIR"
  mkdir -p "$CYCLONEDDS_DIR/build"
  ( cd "$CYCLONEDDS_DIR/build" && cmake .. -DCMAKE_INSTALL_PREFIX=../install && cmake --build . --target install )
  ok "CycloneDDS installiert"
fi
export CYCLONEDDS_HOME="$CYCLONEDDS_DIR/install"

# --- 3. unitree_sdk2 (C++) → SDK2_PREFIX -------------------------------------
log "3/7  unitree_sdk2 (C++) installieren nach $SDK2_PREFIX"
if [ -d "$SDK2_PREFIX/include/unitree" ]; then
  ok "unitree_sdk2 bereits unter $SDK2_PREFIX"
else
  [ -d "$WORKDIR/unitree_sdk2" ] || git clone https://github.com/unitreerobotics/unitree_sdk2.git "$WORKDIR/unitree_sdk2"
  mkdir -p "$WORKDIR/unitree_sdk2/build"
  ( cd "$WORKDIR/unitree_sdk2/build" && cmake .. -DCMAKE_INSTALL_PREFIX="$SDK2_PREFIX" && $SUDO make install )
  ok "unitree_sdk2 installiert"
fi

# --- 4. MuJoCo-Release nach ~/.mujoco ----------------------------------------
log "4/7  MuJoCo $MUJOCO_VERSION nach ~/.mujoco"
MJ_DIR="$HOME/.mujoco/mujoco-$MUJOCO_VERSION"
if [ -d "$MJ_DIR" ]; then
  ok "MuJoCo bereits vorhanden ($MJ_DIR)"
else
  mkdir -p "$HOME/.mujoco"
  MJ_TAR="mujoco-${MUJOCO_VERSION}-linux-x86_64.tar.gz"
  wget -q -O "/tmp/$MJ_TAR" "https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/${MJ_TAR}"
  tar -xzf "/tmp/$MJ_TAR" -C "$HOME/.mujoco"
  rm -f "/tmp/$MJ_TAR"
  ok "MuJoCo entpackt ($MJ_DIR)"
fi

# --- 5. Python-venv + unitree_sdk2_python + mujoco + h2plus ------------------
log "5/7  h2plus-Repo + venv + Python-Pakete"
if [ ! -d "$WORKDIR/H2plus" ]; then
  git clone "$H2PLUS_REPO" "$WORKDIR/H2plus"
fi
VENV="$WORKDIR/H2plus/.venv"
[ -d "$VENV" ] || python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --upgrade pip wheel >/dev/null

# unitree_sdk2_python (braucht CYCLONEDDS_HOME beim Build)
if ! python -c "import unitree_sdk2py" 2>/dev/null; then
  [ -d "$WORKDIR/unitree_sdk2_python" ] || git clone https://github.com/unitreerobotics/unitree_sdk2_python.git "$WORKDIR/unitree_sdk2_python"
  CYCLONEDDS_HOME="$CYCLONEDDS_HOME" pip install -e "$WORKDIR/unitree_sdk2_python"
  ok "unitree_sdk2_python installiert"
else
  ok "unitree_sdk2_python bereits im venv"
fi

pip install "mujoco>=3.1" pygame numpy >/dev/null
ok "mujoco/pygame/numpy installiert"

# h2_loader (unser Stack) inkl. plc-Extra (asyncua)
pip install -e "$WORKDIR/H2plus/.[plc]" >/dev/null
ok "h2_loader installiert (Extra: plc)"

# --- 6. unitree_mujoco (C++-Simulator) bauen ---------------------------------
log "6/7  unitree_mujoco bauen (C++-Simulator)"
if [ ! -d "$WORKDIR/unitree_mujoco" ]; then
  git clone https://github.com/unitreerobotics/unitree_mujoco.git "$WORKDIR/unitree_mujoco"
fi
# MuJoCo-Symlink, den der C++-Build erwartet
[ -e "$WORKDIR/unitree_mujoco/simulate/mujoco" ] || ln -s "$MJ_DIR" "$WORKDIR/unitree_mujoco/simulate/mujoco"
if [ -x "$WORKDIR/unitree_mujoco/simulate/build/unitree_mujoco" ]; then
  ok "unitree_mujoco bereits gebaut"
else
  mkdir -p "$WORKDIR/unitree_mujoco/simulate/build"
  ( cd "$WORKDIR/unitree_mujoco/simulate/build" && cmake .. && make -j"$(nproc)" )
  ok "unitree_mujoco gebaut"
fi

# --- 7. Verifikation ----------------------------------------------------------
log "7/7  Verifikation"
python -c "import mujoco; print('   mujoco', mujoco.__version__)"
python -c "import unitree_sdk2py; print('   unitree_sdk2py OK')" || warn "unitree_sdk2py-Import fehlgeschlagen — CYCLONEDDS_HOME prüfen"
( cd "$WORKDIR/H2plus" && python -m pytest -q ) || warn "pytest nicht vollständig grün — Ausgabe prüfen"

# H2-Modell in unitree_mujoco vorhanden?
if [ -d "$WORKDIR/unitree_mujoco/unitree_robots/h2" ]; then ok "H2-Modell vorhanden (unitree_robots/h2)"; else warn "H2-Modell nicht gefunden — Repo-Stand prüfen"; fi

cat <<EOF

\033[1;32m== Fertig ==\033[0m
Nächste Schritte (zwei Terminals, jeweils venv aktiv:  source "$VENV/bin/activate"):

  1) MuJoCo-H2 starten (GUI, Monitor nötig):
       cd "$WORKDIR/unitree_mujoco/simulate/build" && ./unitree_mujoco -r h2 -s scene_terrain.xml
     ODER Python-Sim:  (config.py -> ROBOT='h2')
       python "$WORKDIR/unitree_mujoco/simulate_python/unitree_mujoco.py"

  2) h2_loader-Bring-up gegen den Twin (headless möglich):
       cd "$WORKDIR/H2plus"
       python -m h2_loader.bringup --iface lo --phase 1     # DDS/LowState aus der Sim (risikolos)
       python -m h2_loader.bringup --iface lo --phase 2     # Loco-FSM in der Sim

Konfig für den Twin: config/robot.sim_mujoco.yaml (driver sdk, iface lo, domain_id 1).
Details/Checkliste: docs/bringup.md (Abschnitt "Digital Twin").
EOF
