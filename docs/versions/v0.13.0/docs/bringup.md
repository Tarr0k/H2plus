# Inbetriebnahme (Bring-up) — Unitree H2 EDU

Schritt-für-Schritt-Checkliste zum sicheren Hochfahren des Unitree H2 EDU mit dem h2_loader-Stack.

> **Hinweis:** Dieses Dokument setzt Stufe B aus `docs/dev_environment.md` voraus (Ubuntu 22.04 LTS, Unitree SDK,
> CycloneDDS 0.10.2 installiert, `pip install -e .[plc]` durchgeführt). Zum Verständnis der Sicherheitskonzepte:
> `docs/safety_concept.md` vor der Inbetriebnahme lesen.

---

## 1. Zweck & Voraussetzungen

### Zweck
Der h2_loader.bringup-Modul verbindet den Roboter schrittweise mit der Steuerungssoftware (DDS-Middleware,
Locomotion-FSM, OPC-UA-SPS-Handshake). Jede Phase ist risikoarm und kann einzeln validiert werden.

### Voraussetzungen — Hardware & Netzwerk

- **Roboter:** Unitree **H2 EDU** (Standard-H2 erlaubt keine SDK-Steuerung)
- **Entwicklungs-PC:** Ubuntu 22.04 LTS; `unitree_sdk2_python`, `cyclonedds 0.10.2` installiert
- **Netzwerk-Setup:**
  - Entwicklungs-PC: `192.168.123.99`
  - H2-Mainboard: `192.168.123.161`
  - PC2 (optional): `192.168.123.162`
  - **Verbindung:** Gigabit-Ethernet (enp3s0 o.ä.)
- **Test vor Inbetriebnahme:** `ping 192.168.123.161` sollte antworten

### Netzwerk prüfen
```bash
# Auf dem Entwicklungs-PC (Ubuntu 22.04)
ip addr show                           # Netzwerk-Interfaces anzeigen (sollte enp3s0 o.ä. sein)
ping -c 3 192.168.123.161              # H2-Mainboard erreichen?
ssh unitree@192.168.123.161            # Optional: SSH zum H2 (Passwort: unitree)
```

Sollte `ping` fehlschlagen: IP-Adressierung oder Kabel-Verbindung prüfen. Mit dem Integrator abklären.

---

## 2. Netzwerk-Setup

### DHCP / Statische IP
Standardmäßig hat das H2-Mainboard die statische IP `192.168.123.161`. Sollte eine andere IP nötig sein,
den Onboard-PC1 via SSH erreichen und `netplan` editieren:

```bash
# SSH als unitree
ssh unitree@192.168.123.161

# Statische IP prüfen
ip addr show                           # aktuell konfigurierte IP
cat /etc/netplan/00-installer-config.yaml

# Falls Änderung nötig: Datei editieren, dann apply
sudo netplan apply
```

### DDS Domain-ID & Interface
Der h2_loader nutzt zwei DDS-Konfigurationen:

| Betrieb | Domain-ID | Netzwerk-Interface | Code |
|---------|-----------|-------------------|------|
| **Real (H2 via Ethernet)** | 0 | `enp3s0` (oder aktuelles Interface) | `ChannelFactoryInitialize(0, "enp3s0")` |
| **Simulator (lokal)** | 1 | Loopback `lo` | `ChannelFactoryInitialize(1, "lo")` |

**Wichtig:** Vor der Inbetriebnahme das korrekte Interface verifizieren:

```bash
ip link show                           # alle Interfaces
ip addr show enp3s0                    # aktuelle IP auf enp3s0
```

### Digital Twin (unitree_mujoco) — H2 ohne echten Roboter simulieren

`unitree_mujoco` ist die MuJoCo-Physiksimulation des H2 von Unitree. Sie stellt **dieselbe DDS-Schnittstelle**
bereit wie der echte Roboter (`rt/lowcmd`, `rt/lowstate`, LocoClient). Dadurch laufen unsere **realen**
Adapter (`UnitreeSdkDriver`, `LocoClientVelocitySink`) **unverändert** gegen die Sim — nur die DDS-Domain/
das Interface wechseln (`domain_id=1`, `lo` statt `enp3s0`). So lassen sich die Bring-up-Phasen 1–3 (und die
Skills) **vor** dem echten Roboter physikalisch validieren.

- ⚠️ **Nur Linux:** Der Unitree-Stack (SDK + CycloneDDS + `unitree_mujoco`) wird nur unter Ubuntu unterstützt
  (Windows/WSL nicht). Es braucht aber **keine GPU und keinen echten Roboter**.
- Ablauf: `unitree_mujoco` starten (H2-Modell), dann den Bring-up mit der Sim-Konfig fahren:

```bash
# 1) In einem Terminal: unitree_mujoco mit H2-Modell starten (siehe dessen README)
# 2) In einem zweiten Terminal, im h2_loader-Repo:
python -m h2_loader.bringup --iface lo --phase 1        # DDS/LowState aus der Sim lesen
python -m h2_loader.bringup --iface lo --phase 2        # Loco-FSM in der Sim
```

Die Zielwerte (Interface `lo`, `domain_id 1`) stehen in **`config/robot.sim_mujoco.yaml`**. Der reine
Logik-Stub (`python -m h2_loader.app --driver sim`) läuft dagegen **ohne** SDK/MuJoCo auch auf Windows —
er testet den Ablauf, nicht die Physik.

---

## 3. Debug-Modus — Pflichtschritt vor SDK-Steuerung

### ⚠️ Kritisch für Bewegung

Das H2-Mainboard startet automatisch das **Motion-Control-Programm** neu. Ohne **Debug-Modus** kollidiert
die SDK-Vorgabe (Befehl vom PC) mit dem Onboard-Regler (Zero-Velocity-Befehle) → **Zittern, unkontrollierte Bewegung**.

**Debug-Modus muss JEDESMAL aktiviert werden, bevor Bewegungsbefehle gesendet werden.**

### Aktivierungsschritte (Fernbedienung)

1. **Aktivieren:** Drücke **L2 + R2** gleichzeitig → LED-Indikator sollte sich verändern
2. **Bestätigen:** Drücke **L2 + A** → Modus bestätigt
3. **Not-Damping (Notfall-Tritt):** **L2 + B** → bremst sofort (für Notfälle)

### Betriebsmodi (Referenz)

Der H2 durchläuft folgende Zustände (nicht manuell gesteuert):
- `Zero-Torque`: Alle Gelenke stromlos
- `Damping`: Passive Dämpfung (sicher zum Anfassen)
- `Ready`: Für Bewegung vorbereitet
- `Motion`: Laufen/Manipulation aktiv
- `Continuous Walking` / `Standing`: Loco-FSM-Zustände
- **`Debug`**: SDK-gesteuert (unser Pfad)

### Bestätigung
Wenn die Phase 0 (s.u.) startet und der Roboter **nicht zittert**, ist Debug-Modus richtig eingestellt.

---

## 4. Sicherheits-Checkliste (vor allen Phasen ≥ 2)

> ⚠️ **Diese Checkliste ist Pflicht, bevor der Roboter sich bewegt.** Sie ersetzt nicht die
> Risikobeurteilung oder zertifizierte Safety-Hardware; sie ist eine funktionale Vorbedingung.
> Vollständiges Konzept: `docs/safety_concept.md`.

| Prüfpunkt | Status | Initiale |
|-----------|--------|----------|
| Freier Bereich um den Roboter (mind. 2m Radius) | ☐ | ____ |
| Not-Halt-Schalter sichtbar und griffbereit | ☐ | ____ |
| Schutzfeld/Lichtgitter aktiviert und getestet | ☐ | ____ |
| Beobachter außerhalb der Roboter-Zone (für Phase 2–3) | ☐ | ____ |
| Debug-Modus aktiv (L2+R2, L2+A) | ☐ | ____ |
| H2-Batterie vollgeladen oder Netzbetrieb | ☐ | ____ |
| Netzwerk-Verbindung stabil (ping erfolgreich) | ☐ | ____ |
| h2_loader venv aktiviert + Abhängigkeiten installiert | ☐ | ____ |
| SPS/OPC-UA-Server erreichbar (für Phase 4) | ☐ | ____ |

**Vor Phase 2/3:** Alle Punkte checken, unterschreiben und dokumentieren.

---

## 5. Bring-up-Phasen

Die Phasen 0–4 bauen aufeinander auf. Sie können einzeln (mit `--phase 0`, `--phase 1`, etc.) oder alle
zusammen (`--phase all`) durchlaufen.

**Befehl-Syntax:**
```bash
cd /path/to/h2_loader  # Repo-Wurzelverzeichnis
source .venv/bin/activate  # Falls noch nicht aktiviert

# Einzelne Phase (Beispiel: Phase 0)
python -m h2_loader.bringup --iface enp3s0 --phase 0

# Alle Phasen (mit Standard-Werten)
python -m h2_loader.bringup --iface enp3s0 --phase all

# Mit zusätzlichen Optionen (siehe unten)
python -m h2_loader.bringup --iface enp3s0 --phase 2 --enable-commanding --yes
```

---

### Phase 0 — Netz & Vorcheck (risikolos)

**Ziel:** Prüfen, dass der Roboter über Netzwerk erreichbar ist und in Debug-Modus läuft.

**Befehl:**
```bash
python -m h2_loader.bringup --iface enp3s0 --phase 0
```

**Erwartetes Ergebnis:**
```
[INFO] Phase 0: Network & Pre-Check
[INFO] Pinging 192.168.123.161 ... OK
[INFO] Checking Debug Mode ...
[INFO] DDS Channel: initialized (domain_id=0, iface=enp3s0)
[INFO] LowState available: 29 joints, IMU, SN: <SN>
[INFO] ✓ Phase 0 passed
```

Die Ausgabe zeigt:
- H2-Mainboard antwortet auf ping
- DDS-Middleware verbunden (29 Gelenke sichtbar)
- IMU aktiv
- Keine Fehler

**Troubleshooting:**

| Problem | Ursache | Lösung |
|---------|--------|--------|
| `Ping timeout` | Netzwerk unterbrochen | Kabel prüfen; `ip link show`; mit Integrator kontaktieren |
| `DDS Channel init failed` | Falschem Interface oder Domain-ID | `--iface enp3s0` (oder anderes); `cyclonedds` neu starten |
| `LowState unavailable` | Debug-Modus nicht aktiv | L2+R2, L2+A auf Fernbedienung; warten 2s; Phase 0 wiederholen |
| `SN unknown / IMU missing` | Hardware-Problem | Onboard-PC1 neu starten (Roboter ausschalten/wieder einschalten); TU erreichen |

---

### Phase 1 — DDS verbinden + Low-State lesen (risikolos)

**Ziel:** Bestätigen, dass alle 29 Gelenke + IMU-Daten live über DDS verfügbar sind.

**Befehl:**
```bash
python -m h2_loader.bringup --iface enp3s0 --phase 1
```

**Erwartetes Ergebnis:**
```
[INFO] Phase 1: DDS Connect & Low-State
[INFO] Subscribing to rt/lowstate ...
[INFO] Received IMUState: accel=[x, y, z], gyro=[gx, gy, gz]
[INFO] Joint 0 (LeftHipPitch): pos=0.12, vel=0.01, tau=0.5
[INFO] Joint 15 (LeftShoulderPitch): pos=0.05, vel=0.02, tau=0.3
... (weitere Gelenke; rechter Arm 22–28) ...
[INFO] ✓ Phase 1 passed — all 29 joints + IMU live
```

Das zeigt:
- Alle 29 Gelenk-Positionen, -Geschwindigkeiten, -Drehmomente live
- IMU-Beschleunigungen und Drehgeschwindigkeiten
- DDS-Schnittstelle funktioniert

**Troubleshooting:**

| Problem | Ursache | Lösung |
|---------|--------|--------|
| `rt/lowstate subscription failed` | DDS-Konfiguration falsch | `cyclonedds` neu starten; `python -m h2_loader.bringup --iface lo --phase 1` (Simulator-Test) |
| `Joint data stale (delay > 100ms)` | Netzwerk-Latenz oder PC1-Last | Warten; mit Integrator abklären |
| `IMU all zeros` | IMU-Sensor nicht kalibriert | Roboter flach auf den Boden stellen, 10s warten; System neu starten |

---

### Phase 2 — Locomotion-FSM: Damp → Start → StandUp (kann bewegen sich)

**Ziel:** Roboter von Damping-Modus über Start zu StandUp hochfahren. **Erste echte Bewegung.**

**Sicherheits-Vorbedingung:**
- ✓ Alle Punkte der Sicherheits-Checkliste (Abschnitt 4) bestätigt
- ✓ Freier Bereich um Roboter
- ✓ Beobachter postiert

**Befehl:**
```bash
python -m h2_loader.bringup --iface enp3s0 --phase 2
```

**Erwartetes Verhalten (Real-Zeit):**
```
[INFO] Phase 2: Locomotion FSM (Damp → Start → StandUp)
[INFO] Creating LocoClient...
[INFO] LocoClient.Init() ...
[INFO] Setting FSM to Damping state ...
[INFO] ✓ Robot in Damping (passive, safe to touch)
[INFO] Setting FSM to Motion/Ready ...
[INFO] ✓ Robot in Motion mode
[INFO] Commanding StandUp...
[INFO] ✓ Robot standing (upright position)
[INFO] ✓ Phase 2 passed
```

Visuell sieht der Roboter:
1. Schlaff (Damping) → läuft in den aufrechten Stand über ~3 Sekunden
2. Bleibt still stehen (StandUp abgeschlossen)

**Troubleshooting:**

| Problem | Verhalten | Ursache | Lösung |
|---------|-----------|--------|--------|
| **Roboter zittert** | Permanentes Zittern in den Beinen | Debug-Modus nicht aktiv | **SOFORT:** L2+R2, L2+A; ggf. Phase 0 wiederholen |
| **Roboter fällt nach schräg** | Schräge Position, kein stabiler Stand | Unebener Boden oder Hardware-Problem | Boden prüfen; Roboter ausschalten/einschalten; mit Integrator kontaktieren |
| **Timeout in StandUp** | Befehl hängt, Roboter bewegt sich nicht | Onboard-Regler nicht bereit | **Notfall:** L2+B (Not-Damping); Phase 0–1 prüfen; neu starten |
| **LocoClient.Init() schlägt fehl** | Sofort abgebrochen | DDS-Fehler oder Debug-Modus aus | Phase 0 bestätigen; Debug-Modus erneut aktivieren |

**Nach erfolgreichem StandUp:**
- Roboter ist stabil im Stand und bereit für Bewegungsbefehle
- Befehle können sofort folgen oder Roboter kann warten
- Zum Stoppen: `Move(0, 0, 0)` oder `StopMove()` senden

---

### Phase 3 — Arm-Home-Fahrt (begrenzt, nur mit `--enable-commanding`)

**Ziel:** Roboterarme vorsichtig in die Ausgangsposition fahren. **Dies ist ein Testlauf**, nicht die volle Manipulation.

**Sicherheits-Vorbedingung:**
- ✓ Phase 2 erfolgreich (Roboter steht sicher)
- ✓ Freier Bereich um die Arme (mind. 50 cm)
- ✓ Beobachter vor Ort

**Befehl (mit `--enable-commanding`):**
```bash
# Mit interaktiver Bestätigung
python -m h2_loader.bringup --iface enp3s0 --phase 3 --enable-commanding

# Ohne Rückfrage (nur wenn Bereich garantiert sicher ist)
python -m h2_loader.bringup --iface enp3s0 --phase 3 --enable-commanding --yes
```

**Erwartetes Verhalten:**
```
[WARNING] Phase 3 requires --enable-commanding
[WARNING] *** Arm motion will be commanded ***
[WARNING] Ensure free space around arms (50cm minimum)
[WARNING] Continue? [y/N]: y

[INFO] Creating low-level arm control...
[INFO] Commanding arm home position (clamped, low torque)...
[INFO] Left arm: moving towards home...
[INFO] Right arm: moving towards home...
[INFO] ... (5–10 Sekunden Bewegung) ...
[INFO] ✓ Phase 3 passed — arms at home position
```

**Konservative Begrenzungen in Phase 3:**
- Arme fahren **langsam** (25% maximale Geschwindigkeit)
- Drehmomente **geclampt** (30% max. Torque)
- Nur die **Home-Position**, nicht volle Manipulation
- Bei Kontakt → sofort Befehl stoppen

**Troubleshooting:**

| Problem | Symptom | Ursache | Lösung |
|---------|---------|--------|--------|
| `--enable-commanding not set` | Befehl wird ignoriert | Flag vergessen | `--enable-commanding` explizit hinzufügen |
| **Arme bewegen sich ruckartig** | Unkontrollierte Bewegung, zuckend | Torque-Limits nicht aktiv oder Debug-Modus-Problem | **STOP:** L2+B; neu starten; Phase 0 prüfen |
| **Arm bleibt stecken** | Bewegung bricht ab, kein Fehler | Mechanischer Block oder Onboard-Regler Schutz | Roboter ausschalten, prüfen, neu starten |
| `Phase 3 skipped (flag missing)` | Befehl erfolgreich, aber nichts passiert | `--enable-commanding` nicht gesetzt | normale Reaktion; Befehl mit Flag erneut ausführen |

**Nach erfolgreichem Arm-Home:**
- Arme sind in der Ausgangsposition
- Bereit für volle Manipulationsbefehle (in einer produktiven Skill)

---

### Phase 4 — OPC-UA-SPS-Handshake (Verbindung zur Steuerung)

**Ziel:** Verbindung zur PLC/SPS über OPC-UA prüfen. Heartbeat testen. Round-Trip verifizieren.

**Sicherheits-Vorbedingung:**
- ✓ OPC-UA-Server (PLC) läuft und ist erreichbar
- ✓ IP/Port bekannt

**Befehl (mit `--endpoint`):**
```bash
# Beispiel: OPC-UA-Server auf 192.168.123.100:4840
python -m h2_loader.bringup --iface enp3s0 --phase 4 --endpoint "opc.tcp://192.168.123.100:4840"

```

**Erwartetes Ergebnis:**
```
[INFO] Phase 4: OPC-UA Handshake
[INFO] Connecting to opc.tcp://192.168.123.100:4840 ...
[INFO] ✓ OPC-UA connection established
[INFO] Reading H2 Handshake UDT...
[INFO]   robotEnable: True
[INFO]   safeZoneClear: True
[INFO]   robotInMachine: False
[INFO] ✓ Heartbeat exchange (local ↔ PLC): 50 ms round-trip
[INFO] ✓ Writing robotInMachine := True
[INFO] ✓ Reading back: robotInMachine := True
[INFO] ✓ Phase 4 passed
```

Das zeigt:
- OPC-UA-Verbindung stabil
- Alle H2 Handshake-Tags lesbar und schreibbar
- Heartbeat funktioniert
- Round-Trip < 200 ms (akzeptabel)

**Troubleshooting:**

| Problem | Symptom | Ursache | Lösung |
|---------|---------|--------|--------|
| `OPC-UA connection failed` | Sofort abgebrochen | PLC offline oder falsche Adresse | `--endpoint` prüfen; PLC kontaktieren; `ping 192.168.123.100` |
| `Cannot read H2 Handshake UDT` | Verbindung OK, aber UDT nicht sichtbar | UDT-Struktur nicht in PLC vorhanden | mit Integrator prüfen; TIA-Projekt-Version prüfen |
| `Heartbeat timeout` | Liest UDT, aber Heartbeat-Signal bleibt stecken | PLC sendet keinen Toggle-Impuls | PLC-Programm prüfen; H2HandshakeServer aktiv? |
| `Round-trip > 500 ms` | Langsame Kommunikation | Netzwerk-Last oder PLC-Blockade | Netzwerk prüfen; PLC-Last reduzieren |

**Detaillierte Netzwerk-Diagnose:**
```bash
# OPC-UA-Port prüfen (typisch 4840)
nc -zv 192.168.123.100 4840                    # Verbindung möglich?
netstat -an | grep 4840                        # Lokale Listener?

# Latenz prüfen
ping -c 5 192.168.123.100                      # Ping-Latenz (sollte < 50 ms sein)
```

---

## 6. Empfohlene Reihenfolge & Ablauf

### Für die **erste Inbetriebnahme**

1. **Preparation (offline)**
   - Netzwerk-Setup prüfen (`ping 192.168.123.161`)
   - Alle Abhängigkeiten installiert? (`pip install -e .[plc]`)
   - h2_loader.venv aktiviert?

2. **Hardware-Check (ohne Bewegung)**
   - Phase 0: `python -m h2_loader.bringup --iface enp3s0 --phase 0`
   - Phase 1: `python -m h2_loader.bringup --iface enp3s0 --phase 1`
   - ✓ Roboter kommuniziert und LowState sichtbar

3. **Bewegung-Test (mit Sicherheits-Checkliste)**
   - Sicherheits-Checkliste aus Abschnitt 4 unterschreiben
   - Debug-Modus aktivieren (L2+R2, L2+A)
   - Phase 2: `python -m h2_loader.bringup --iface enp3s0 --phase 2`
   - ✓ Roboter steht, keine Bewegungsfehler

4. **Arm-Test (optional, nur wenn nötig)**
   - Freier Bereich um Arme checken
   - Phase 3: `python -m h2_loader.bringup --iface enp3s0 --phase 3 --enable-commanding --yes`
   - ✓ Arme in Home-Position

5. **SPS-Kopplung (wenn Integrator bereit)**
   - PLC online und erreichbar
   - Phase 4: `python -m h2_loader.bringup --iface enp3s0 --phase 4 --endpoint "opc.tcp://..."
   - ✓ Heartbeat läuft, Tags lesbar

### Für schnelle Wiederholungstests

Nach erfolgreicher erstes Mal:

```bash
# Alle Phasen ohne Kommandieren (schneller, risikolos)
python -m h2_loader.bringup --iface enp3s0 --phase all

# Oder gezielt einzelne Phase neu testen
python -m h2_loader.bringup --iface enp3s0 --phase 2
```

---

## 7. Nach erfolgreichem Bring-up

### Nächste Schritte

1. **Skill-Entwicklung:** Mit dem Roboter können jetzt `h2_loader.skills.*` (Load, Unload, HandChange, etc.)
   entwickelt und getestet werden. Details: `docs/architecture.md`.

2. **GR00T-Pfad:** Für die künftige autonome Lernfähigkeit des Roboters (NVIDIA Isaac GR00T):
   `docs/groot_setup.md` und `docs/roadmap_groot.md` nachschlagen.

3. **Produktion-Checklist:** Vor dem produktiven Einsatz an der Induktionshärtemaschine:
   - Komplette Risikobeurteilung (ISO 12100) durchführen
   - Safety-SPS installieren und prüfen
   - Alle Schutzeinrichtungen (Lichtgitter, Not-Halt) testen
   - Bedien-Personal schulen
   - Inbetriebnahmeprotokoll dokumentieren

### Wiederholte Inbetriebnahme (täglich)

```bash
# Schneller Check vor jedem Arbeitstag
python -m h2_loader.bringup --iface enp3s0 --phase all --yes

# Oder manuell interaktiv (mit Rückfragen)
python -m h2_loader.bringup --iface enp3s0 --phase all
```

### Notfall-Procedures

| Situation | Befehl | Folge |
|-----------|--------|-------|
| **Roboter bewegt sich unkontrolliert** | L2+B (Fernbedienung) | Sofort Damping, passive Bremsen |
| **Netzwerk-Unterbruch während Bewegung** | (automatisch) | Roboter fährt zu Damping über Timeout |
| **OPC-UA-Verbindung abbricht** | `SafetySupervisor` blockt | Roboter fährt in sicheren Zustand; Heartbeat-Timeout |

Alles weitere: `docs/safety_concept.md` Abschnitt 5 (Reaktionsmatrix).

---

## 8. Weitere Ressourcen

- **Entwicklung:** `docs/dev_environment.md` (Stufe A/B/C)
- **SDK-Details:** `docs/sdk_reference.md`
- **Sicherheit:** `docs/safety_concept.md`
- **Skills:** `docs/architecture.md` (nach Bring-up)
- **GR00T Zukunft:** `docs/groot_setup.md`, `docs/roadmap_groot.md`

---

**Version:** 1.0  
**Gültig ab:** 2026-07-03  
**Nächste Überprüfung:** Nach ersten Live-Tests
