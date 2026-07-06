#!/usr/bin/env bash
# =============================================================================
# ematalos: SSH-Key-Login + passwortloses sudo für Benutzer 'ema' einrichten
# =============================================================================
# AUF DEM UBUNTU-RECHNER (ematalos) ALS BENUTZER 'ema' AUSFÜHREN:
#     bash enable_ssh_sudo.sh
# Fragt EINMAL das sudo-Passwort ab (für den sudoers-Eintrag).
#
# Danach kann sich der zugehörige Rechner ohne Passwort per SSH anmelden und
# das Setup-Skript (scripts/setup_ubuntu_twin.sh) non-interaktiv laufen lassen.
#
# ⚠️ Sicherheit: NOPASSWD:ALL ist weitreichend. Rückgängig:
#     sudo rm /etc/sudoers.d/010-ema-nopasswd
#     # und die Key-Zeile 'h2plus-ematalos-access' aus ~/.ssh/authorized_keys löschen
# Der Public Key ist nicht geheim (öffentlicher Schlüssel); der PRIVATE Key
# verbleibt ausschließlich auf dem zugreifenden Rechner.
# =============================================================================
set -euo pipefail

# Public Key des zugreifenden Rechners (Windows-Dev, h2plus):
PUBKEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIk8RbO64awjQ7a+hW6Cl3X8s4yRcObmW8wAoNTetiFN h2plus-ematalos-access'
TARGET_USER="${TARGET_USER:-ema}"

echo "== 1/2  Public Key in ~/.ssh/authorized_keys eintragen =="
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys" && chmod 600 "$HOME/.ssh/authorized_keys"
if grep -qF "$PUBKEY" "$HOME/.ssh/authorized_keys"; then
  echo "   Key bereits vorhanden — nichts zu tun."
else
  printf '%s\n' "$PUBKEY" >> "$HOME/.ssh/authorized_keys"
  echo "   Key hinzugefügt."
fi

echo "== 2/2  Passwortloses sudo für '$TARGET_USER' einrichten =="
TMP="$(mktemp)"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "$TARGET_USER" > "$TMP"
if sudo visudo -cf "$TMP" >/dev/null; then
  sudo install -m 0440 -o root -g root "$TMP" "/etc/sudoers.d/010-${TARGET_USER}-nopasswd"
  echo "   /etc/sudoers.d/010-${TARGET_USER}-nopasswd installiert."
else
  echo "   FEHLER: sudoers-Validierung fehlgeschlagen — nichts geändert." >&2
  rm -f "$TMP"; exit 1
fi
rm -f "$TMP"

echo "== Selbsttest =="
if sudo -n true 2>/dev/null; then
  echo "   OK: 'sudo' ohne Passwort aktiv."
else
  echo "   WARN: 'sudo -n' fehlgeschlagen — bitte prüfen."
fi

echo
echo "Fertig. Vom Dev-Rechner testen:  ssh ema@100.68.27.117 whoami"
