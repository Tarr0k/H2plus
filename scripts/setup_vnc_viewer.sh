#!/usr/bin/env bash
# =============================================================================
# TigerVNC-Desktop (:2) mit automatischem H2-MuJoCo-Viewer (Ubuntu, über Tailscale)
# =============================================================================
# Auf dem Ubuntu-Rechner als Zielbenutzer ausführen — NACH scripts/setup_ubuntu_twin.sh.
# Richtet einen leichten VNC-Desktop (openbox) ein, der beim Start automatisch den
# H2 im Standard-MuJoCo-Viewer öffnet. Erreichbar über die Tailscale-IP:5902.
#
# Erkenntnis (wichtig): Der MuJoCo-Viewer öffnet KEIN Fenster, wenn man ihn über eine
# detachte SSH-Sitzung startet — er muss AUS der Desktop-Session heraus laufen. Genau
# das macht der xstartup-Eintrag hier.
#
# Konfiguration per Env (Defaults):
#   DISPLAY_NUM(2) GEOMETRY(1600x900) VNC_PASSWORD(h2talos-view — bitte ändern!)
#   H2PLUS(~/H2plus) UNITREE_MUJOCO(~/unitree_mujoco)
#   SCENE(<UNITREE_MUJOCO>/unitree_robots/h2/scene.xml) VENV_PY(<H2PLUS>/.venv/bin/python)
# =============================================================================
set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-2}"
GEOMETRY="${GEOMETRY:-1600x900}"
VNC_PASSWORD="${VNC_PASSWORD:-h2talos-view}"
H2PLUS="${H2PLUS:-$HOME/H2plus}"
UNITREE_MUJOCO="${UNITREE_MUJOCO:-$HOME/unitree_mujoco}"
SCENE="${SCENE:-$UNITREE_MUJOCO/unitree_robots/h2/scene.xml}"
VENV_PY="${VENV_PY:-$H2PLUS/.venv/bin/python}"
PORT=$((5900 + DISPLAY_NUM))

export DEBIAN_FRONTEND=noninteractive
echo "== Pakete (TigerVNC + openbox + xterm + mesa) =="
sudo -n apt-get install -y -qq tigervnc-standalone-server tigervnc-common openbox xterm x11-xserver-utils libgl1-mesa-dri mesa-utils

echo "== VNC-Passwort =="
mkdir -p ~/.config/tigervnc && chmod 700 ~/.config/tigervnc
printf '%s\n' "$VNC_PASSWORD" | vncpasswd -f > ~/.config/tigervnc/passwd
chmod 600 ~/.config/tigervnc/passwd

echo "== xstartup (openbox + xterm + H2-Viewer-Autostart) =="
SCENE_DIR="$(dirname "$SCENE")"; SCENE_FILE="$(basename "$SCENE")"
cat > ~/.config/tigervnc/xstartup <<EOF
#!/bin/sh
unset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS
xsetroot -solid grey 2>/dev/null
xterm -geometry 100x28+20+20 &
( cd "$SCENE_DIR" && exec "$VENV_PY" -m mujoco.viewer --mjcf="$SCENE_FILE" >/tmp/mjview.log 2>&1 ) &
exec openbox
EOF
chmod +x ~/.config/tigervnc/xstartup

echo "== ufw: eingehend nur über tailscale0 =="
sudo -n ufw allow in on tailscale0 >/dev/null 2>&1 || true

echo "== VNC :$DISPLAY_NUM (neu) starten =="
vncserver -kill ":$DISPLAY_NUM" >/dev/null 2>&1 || true
sleep 1; rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}" 2>/dev/null || true
vncserver ":$DISPLAY_NUM" -geometry "$GEOMETRY" -depth 24 -localhost no -SecurityTypes VncAuth

echo
echo "Fertig. VNC-Viewer verbinden auf  <tailscale-ip>:$PORT  (Display :$DISPLAY_NUM), Passwort: $VNC_PASSWORD"
echo "Der H2 sollte im MuJoCo-Fenster stehen. Passwort ändern: vncpasswd"
