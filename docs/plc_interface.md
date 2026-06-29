# OPC-UA-Schnittstelle zur SPS — H2 PLUS an Induktionshärtemaschine

## Zweck & Topologie

Der **Unitree H2 PLUS** kommuniziert mit einer **Siemens S7-1500 SPS**, die die Induktionshärtemaschine
steuert. Die Kommunikation läuft über **OPC UA** — die S7-1500 agiert als OPC-UA-Server (integriert, keine
zusätzliche Runtime nötig), der H2 (Python-Client auf Ubuntu 22.04) fungiert als OPC-UA-Client und verbindet
sich über `asyncua`.

Die **Schnittstelle** ist als TIA-Datenblock mit einer strukturierten UDT abgelegt:

- **DB:** `H2_Interface_DB` (in der SPS, "aus OPC UA erreichbar" markiert, optimierter DB ok)
- **Member:** `iface : H2Interface_UDT`

Diese Struktur wird 1:1 gespiegelt in der Python-Seite:
- **TIA-Definition:** `tia/udt/H2_Interface_UDTs.scl`
- **Python-Pendant:** `src/h2_loader/plc/udt.py` (Feldkatalog) + `src/h2_loader/plc/handshake.py` (Ablauflogik)

Die Kommunikation ist **nicht echtzeitfähig** — OPC UA pollt, die SPS lebt weiter, der Client (H2) ist
untergeordnet und reagiert auf Zustandswechsel.

---

## Grundprinzipien

### Toggle-Handshake statt Impulse

OPC UA kennt keinen echten Event-Push. Daher verwenden wir **Toggle-basierte Flanken-Erkennung** für
kritische Signale (Auftragsannahme, -fertigstellung):

- Die **SPS setzt** ein Signal (z. B. `jobReqToggle := NOT jobReqToggle`) als Flankensignal
- Der **H2-Client pollt** periodisch und detektiert die Flanke (Wechsel des Boolean-Werts)
- Der H2 **antwortet** mit eigenem Toggle (z. B. `jobAckToggle`), um Quittung zu signalisieren

Dies ist zuverlässig und entkoppelt von Pollfrequenz und Netzwerkverzögerung.

### Bidirektionales Heartbeat

Beide Seiten senden ein **monoton steigendes Counter-Signal** (meist eine `UInt`, Rollover akzeptiert):
- **SPS → H2:** `plcHeartbeat` — zeigt, dass die SPS läuft
- **H2 → SPS:** `robotHeartbeat` — zeigt, dass der H2-Client aktiv ist

Jede Seite beobachtet das gegenseitige Signal. Ein ausbleibender Heartbeat über einen definierten Timeout
(z. B. 2–3 Sekunden) signalisiert Konnektivitätsverlust und triggert Notfall-Recovery.

### Versionsfeld & gegenseitige Verriegelung

- **`interfaceVersion`** (SPS → H2): Versionsnummer des Schnittstellen-Protokolls. Der H2-Client prüft
  diese beim Verbindungsaufbau und lehnt inkompatible Versionen ab.
- **`robotInMachine`** (H2 → SPS): Bool-Signal, das anzeigt, „Roboter arbeitet derzeit in der Maschine".
  Die SPS blockiert damit jegliche Maschinensteuerung von Hand oder extern, solange der H2 aktiv ist.

---

## SICHERHEIT ⚠️

**OPC UA ist nicht sicherheitsgerichtet.** Dies ist eine funktionale Schnittstelle für Automatisierung,
**nicht** für den Schutz vor Verletzungen.

### Echte Sicherheit läuft hardwired

Der echte **Not-Halt** und die **Bereichsfreigabe** (Safe Zone Clear) laufen über eine dedizierte
**Safety-SPS (F-Modul oder Siemens Safety Integrated)** mit zweikanal igen, zertifizierten Signalen:

- **Not-Halt-Taste** (manuell gedrückt) → **hardwired Safety-Schütz** → **Maschinenantrieb sofort aus**
- **Bereichs-Lichtgitter** oder **Zweitaster** → **zertifizierter Sicherheitskreis** → **Roboter-Bewegung sofort blockiert**

### Die UDT-Safety-Member sind funktionale Spiegel

Die Felder in der `safety`-Sektion der UDT (`estopFromPlc`, `estopFromRobot`, `safeZoneClear`, `robotEnable`,
`watchdogFault`) sind **Ablauf-Echo für die Automation**, nicht die Quelle der Sicherheit:

- Sie helfen der Ablauflogik, den Sicherheitszustand nachzuvollziehen
- Sie ermöglichen diagnostische Ausgaben im HMI
- Sie sind für statistische Auswertung und Fehlersuche da

**Aber:** Sicherheitsgerichtete Entscheidungen (Maschinenantrieb stoppen, Roboter in Homeposition fahren)
müssen auf der **SPS-Seite, im Sicherheitskreis** getroffen werden, nicht im Python-Code des H2.

### Best Practice

1. Der H2-Client überwacht den `watchdogFault`-Flag und die Safety-Echos zur **Diagnose**
2. Sämtliche **sicherheitsgerichteten Aktionen** (Maschinenantrieb deaktivieren, Not-Halt auslösen) müssen
   von der SPS initiiert werden
3. Bei Konnektivitätsverlust (`robotHeartbeat` ausfallen) → SPS stoppt die Maschine **automatisch**
4. Der H2-Client darf sich **nie** verlassen auf: OPC-UA-Verbindung, Netzwerk oder Python-Software für
   Sicherheitsfunktionen

---

## UDT-Struktur

Die `H2Interface_UDT` ist hierarchisch aufgebaut:

```
H2Interface_UDT
├── control            (bidirektional / Verwaltung)
├── plcToRobot         (SPS → H2)
├── robotToPlc         (H2 → SPS)
└── safety             (funktionale Spiegel, beide Seiten)
```

Jede Unter-Struktur wird als separate Tabelle dokumentiert.

### control — Verwaltung & Heartbeat

| Member | Typ | Richtung | Bedeutung |
|--------|-----|----------|-----------|
| `interfaceVersion` | UInt | SPS → H2 | Versionsnummer der Schnittstelle (z. B. 0x0001). H2-Client prüft Kompatibilität beim Start. |
| `plcHeartbeat` | UInt | SPS → H2 | Monoton steigende Zahl (0…65535, Rollover ok). Jede Sekunde um ≥1 erhöht. Zeigt SPS-Aktivität. |
| `robotHeartbeat` | UInt | H2 → SPS | Monoton steigende Zahl. H2-Client erhöht jede Sekunde um ≥1. Zeigt H2-Verbindung. |
| `plcAlive` | Bool | H2 → SPS | Wird von H2 aus `plcHeartbeat` abgeleitet. Timeout ~3 Sekunden. |
| `robotAlive` | Bool | SPS → H2 | Wird von SPS aus `robotHeartbeat` abgeleitet. Timeout ~3 Sekunden. |
| `robotConnected` | Bool | H2 → SPS | True, wenn H2-Client mit OPC-UA-Server verbunden ist. |
| `operatingMode` | Int | SPS → H2 | Betriebsmodus: 0=Aus, 1=Hand, 2=Auto, 3=Einrichten. Der H2 respektiert diese Vorgabe. |

### plcToRobot — Anforderungen SPS → H2

| Member | Typ | Richtung | Bedeutung |
|--------|-----|----------|-----------|
| `jobRequest` | Int | SPS → H2 | Arbeitsauftrag-Typ: 0=keiner, 1=Laden (Pick), 2=Entladen (Place), 3=Induktorwechsel |
| `jobId` | DInt | SPS → H2 | Eindeutige Auftrags-ID. Inkrementiert bei neuem Auftrag. |
| `partType` | Int | SPS → H2 | Werkstück-Typ (z. B. 0=Standard, 1=Spezial). Für zukunftige Varianten. |
| `jobReqToggle` | Bool | SPS → H2 | **Flankensignal.** SPS invertiert dieses Bit, wenn ein neuer Auftrag gesetzt wird. H2 erkennt Flanke = neuer Auftrag. |
| `machineReady` | Bool | SPS → H2 | True: Maschine ist in Grundzustand (Tür offen, Spannvorrichtung leer). |
| `doorOpen` | Bool | SPS → H2 | True: Maschinen-Einladeöffnung ist offen. |
| `doorClosed` | Bool | SPS → H2 | True: Maschinen-Einladeöffnung ist geschlossen (Sensor bestätigt). |
| `clampOpen` | Bool | SPS → H2 | True: Spannvorrichtung ist offen. |
| `clampClosed` | Bool | SPS → H2 | True: Spannvorrichtung ist geschlossen (Sensor bestätigt). |
| `machineCycleRun` | Bool | SPS → H2 | True: Maschinen-Härtezyklus läuft gerade. |
| `machineFault` | Bool | SPS → H2 | True: Maschine meldet Fehler. H2 soll abbrechen. |
| `zoneFreeForRobot` | Bool | SPS → H2 | True: Arbeitsbereich ist freigegeben, keine Sicherheitsfreigabe aktiv. |
| `partInClamp` | Bool | SPS → H2 | True: Sensor meldet, ein Werkstück sitzt in der Spannvorrichtung. |

### robotToPlc — Zustand & Anforderungen H2 → SPS

| Member | Typ | Richtung | Bedeutung |
|--------|-----|----------|-----------|
| `robotState` | Int | H2 → SPS | Roboter-Zustand: 0=Init, 1=Idle, 2=Busy (führt Auftrag aus), 3=Done (fertig), 4=Error, 5=NotReady (kein Client). |
| `jobIdEcho` | DInt | H2 → SPS | Echo der empfangenen `jobId`. SPS vergleicht: wenn `jobIdEcho ≠ jobId`, war Übertragung unsicher. |
| `jobAckToggle` | Bool | H2 → SPS | **Flankensignal.** H2 invertiert dieses, wenn Auftrag akzeptiert wurde (Preconditions ok). |
| `jobDoneToggle` | Bool | H2 → SPS | **Flankensignal.** H2 invertiert dieses, wenn Auftrag fertig (erfolgreich oder Fehler). |
| `jobResult` | Int | H2 → SPS | Ergebnis des letzten Auftrags: 0=offen, 1=OK (erfolgreich), 2=NOK (Fehler). |
| `currentStep` | Int | H2 → SPS | Debug-Info: Welcher Skill-Schritt läuft gerade (z. B. 10=Tür-Warten, 20=Bewegung, 30=Greifen). |
| `reqOpenDoor` | Bool | H2 → SPS | H2 **fordert an:** Bitte Tür öffnen. SPS öffnet, bestätigt via `doorOpen`. |
| `reqCloseDoor` | Bool | H2 → SPS | H2 **fordert an:** Bitte Tür schließen. SPS schließt, bestätigt via `doorClosed`. |
| `reqOpenClamp` | Bool | H2 → SPS | H2 **fordert an:** Bitte Spannvorrichtung öffnen. SPS antwortet via `clampOpen`. |
| `reqCloseClamp` | Bool | H2 → SPS | H2 **fordert an:** Bitte Spannvorrichtung schließen. SPS antwortet via `clampClosed`. |
| `robotReady` | Bool | H2 → SPS | True: H2 ist initialisiert, bereit zu arbeiten. |
| `robotBusy` | Bool | H2 → SPS | True: H2 führt gerade eine Bewegung aus (schneller als `robotState=2`, für HMI-Anzeige). |
| `gripperHoldsPart` | Bool | H2 → SPS | True: Greifer hält Werkstück (Drucksensor oder Endeffektor-Feedback). |
| `robotInMachine` | Bool | H2 → SPS | True: Roboter-Arm befindet sich im Arbeitsbereich der Maschine. **SPS blockiert damit externe/manuelle Maschinenbedienung.** |
| `errorActive` | Bool | H2 → SPS | True: H2 meldet internen Fehler (Netzwerk, Motion-Fehler, Skill-Fehler). |
| `errorCode` | DInt | H2 → SPS | Fehler-Code (für Diagnose / Log). |

### safety — Funktionale Spiegel (beide Seiten)

| Member | Typ | Richtung | Bedeutung |
|--------|-----|----------|-----------|
| `estopFromPlc` | Bool | SPS → H2 | True: SPS hat Not-Halt empfangen (Sicherheitskreis). H2 antwortet mit STOP aller Bewegungen. |
| `estopFromRobot` | Bool | H2 → SPS | True: H2-interner Fehler führte zu Notfall-Stop (z. B. Quetschen erkannt). SPS erhöht Aufmerksamkeit. |
| `safeZoneClear` | Bool | SPS → H2 | True: Sicherheits-Lichtgitter / Bereichs-Sensor meldet, Bereich ist frei. |
| `robotEnable` | Bool | SPS → H2 | True: Zertifizierter Sicherheitskreis hat H2-Bewegung freigegeben. |
| `watchdogFault` | Bool | SPS → H2 | True: Sicherheits-Watchdog meldet Fehler (ungültige Verdrahtung, Timeout im Safety-Modul). |

---

## Auftrags-Handshake (Sequenz)

Der Auftrag folgt einer nummerierten Abfolge mit Toggle-Flanken für sichere Erkennung:

```
1. SPS wartet auf Vorbedingung (machineReady ∧ ¬robotInMachine ∧ ¬machineFault)

2. SPS setzt neuen Auftrag:
   jobRequest := <1|2|3>
   jobId += 1
   partType := <gemäß Maschinenlogik>
   jobReqToggle := NOT jobReqToggle   ← FLANKE, neue Aufträge signalisieren

3. H2 pollt OPC UA, erkennt Flankenwechsel in jobReqToggle

4. H2 prüft Vorbedingungen für diesen Auftrag:
   - operatingMode == 2 (Auto)?
   - robotAlive ∧ estopFromPlc == False?
   - Passt jobRequest zu aktueller Roboter-Config?

5. Falls OK → H2 akzeptiert:
   jobIdEcho := jobId
   jobAckToggle := jobReqToggle   ← Echo-Flanke, Quittung
   robotState := 2 (Busy)

6. Falls NICHT OK (Precondition failed) → H2 lehnt ab:
   jobResult := 2 (NOK)
   jobDoneToggle := NOT jobDoneToggle
   robotState := 4 (Error) oder 5 (NotReady)

7. Falls akzeptiert, H2 führt aus:
   - Ruft Skill auf (load/unload/change_inductor)
   - Beobachtet Zustandssignale (doorOpen, clampClosed, etc.)
   - Fordert bei Bedarf an: reqOpenDoor, reqCloseDoor, reqOpenClamp, reqCloseClamp
   - SPS reagiert auf diese Requests (Aktor betätigen, dann Bool-Feedback setzen)
   - currentStep wird inkrementiert zur Fehlersuche

8. Skill fertig (erfolgreich oder Fehler):
   jobResult := 1 (OK) oder 2 (NOK)
   jobDoneToggle := NOT jobDoneToggle   ← FLANKE, Fertigmeldung
   robotState := 3 (Done)

9. SPS erkennt Flankenwechsel in jobDoneToggle
   
10. SPS quittiert Verarbeitung:
    jobRequest := 0 (keiner)
    (optional: robotState-Echo setzen)

11. H2 erkennt jobRequest == 0, kehrt in Idle:
    robotState := 1 (Idle)

```

**Wichtig:** Der gesamte Handshake ist **idempotent** — wiederholtes Übertragen derselben Flanke führt nicht
zu mehrfacher Ausführung, da beide Seiten die Flanke (Wechsel) nutzen, nicht den Wert selbst.

---

## NodeId-Schema (OPC UA)

Die OPC-UA-NodeIds für die Schnittstellen-Member folgen diesem Muster:

```
ns=3;s="H2_Interface_DB"."iface"."<sektion>"."<member>"
```

Beispiele:

- `ns=3;s="H2_Interface_DB"."iface"."control"."plcHeartbeat"`
- `ns=3;s="H2_Interface_DB"."iface"."plcToRobot"."jobRequest"`
- `ns=3;s="H2_Interface_DB"."iface"."robotToPlc"."robotState"`
- `ns=3;s="H2_Interface_DB"."iface"."safety"."estopFromPlc"`

**Konfiguration in TIA Portal V20:**

1. CPU (z. B. 1500F oder 1500S) auswählen
2. Eigenschaften → OPC UA → Allgemein → **„OPC UA aktivieren"** ✓
3. Den DB `H2_Interface_DB` markieren → Eigenschaften → **„Aus OPC UA erreichbar"** ✓
4. (Optional) Symbolische Adressierung für bessere Lesbarkeit: Kann auch optimierter DB sein, solange
   die TIA-Variablenliste die Symbole exportiert
5. Projekt kompilieren und auf CPU laden

Der H2-Client verbindet sich zum OPC-UA-Endpoint der CPU (z. B. `opc.tcp://192.168.100.1:4840`) und
benutzt diese NodeIds zum Lesen/Schreiben.

---

## Wertetabellen — Codierte Felder

### jobRequest (Int, SPS → H2)

| Wert | Bedeutung |
|------|-----------|
| 0 | Kein Auftrag |
| 1 | Laden (Pick): Werkstück aus Input-Quelle in Maschine laden |
| 2 | Entladen (Place): Werkstück aus Maschine in Output-Position entladen |
| 3 | Induktorwechsel: Aktuellen Induktor wechseln (zukünftige Funktion) |

### robotState (Int, H2 → SPS)

| Wert | Bedeutung |
|------|-----------|
| 0 | Init: H2-Client startet gerade, nicht bereit |
| 1 | Idle: H2 wartet auf Auftrag, ist aber betriebsbereit |
| 2 | Busy: Auftrag wird gerade ausgeführt |
| 3 | Done: Auftrag abgeschlossen (Ergebnis in `jobResult` prüfen) |
| 4 | Error: Interner Fehler (s. `errorCode`). H2 benötigt Neustart oder Reset. |
| 5 | NotReady: OPC-UA-Client nicht verbunden oder nicht initialisiert. |

### jobResult (Int, H2 → SPS)

| Wert | Bedeutung |
|------|-----------|
| 0 | Offen: Auftrag läuft noch oder wurde nicht gestartet |
| 1 | OK: Auftrag erfolgreich abgeschlossen |
| 2 | NOK: Auftrag fehlgeschlagen (Precondition nicht erfüllt oder Skill-Fehler während Ausführung) |

### operatingMode (Int, SPS → H2)

| Wert | Bedeutung |
|------|-----------|
| 0 | Aus: H2 soll alle Bewegungen stoppen, nur Heartbeat aufrecht erhalten |
| 1 | Hand: Manuelle Bedienung (über separate Joystick/Teach-Hardware), H2 folgt nicht |
| 2 | Auto: H2 akzeptiert Aufträge von SPS und führt diese aus |
| 3 | Einrichten: Teach-Modus. H2 akzeptiert nur Bewegungsbefehle für Posen-Aufzeichnung. |

---

## Python-Anbindung

Die UDT wird in der Python-Seite an zwei Stellen gespiegelt:

### 1. UDT-Feldkatalog (`src/h2_loader/plc/udt.py`)

```python
# Beispiel-Struktur (vereinfacht)
class H2InterfaceControl(BaseModel):
    interface_version: int      # → TIA: interfaceVersion
    plc_heartbeat: int          # → TIA: plcHeartbeat
    robot_heartbeat: int        # → TIA: robotHeartbeat
    plc_alive: bool
    robot_alive: bool
    robot_connected: bool
    operating_mode: int

class H2InterfacePlcToRobot(BaseModel):
    job_request: int            # → TIA: jobRequest
    job_id: int                 # → TIA: jobId
    part_type: int
    job_req_toggle: bool        # → TIA: jobReqToggle (FLANKE)
    machine_ready: bool
    door_open: bool
    door_closed: bool
    clamp_open: bool
    clamp_closed: bool
    machine_cycle_run: bool
    machine_fault: bool
    zone_free_for_robot: bool
    part_in_clamp: bool

class H2InterfaceRobotToPlc(BaseModel):
    robot_state: int            # → TIA: robotState
    job_id_echo: int            # → TIA: jobIdEcho
    job_ack_toggle: bool        # → TIA: jobAckToggle (FLANKE)
    job_done_toggle: bool       # → TIA: jobDoneToggle (FLANKE)
    job_result: int             # → TIA: jobResult
    current_step: int           # → TIA: currentStep
    req_open_door: bool
    req_close_door: bool
    req_open_clamp: bool
    req_close_clamp: bool
    robot_ready: bool
    robot_busy: bool
    gripper_holds_part: bool
    robot_in_machine: bool
    error_active: bool
    error_code: int

class H2InterfaceSafety(BaseModel):
    estop_from_plc: bool        # → TIA: estopFromPlc
    estop_from_robot: bool      # → TIA: estopFromRobot
    safe_zone_clear: bool       # → TIA: safeZoneClear
    robot_enable: bool          # → TIA: robotEnable
    watchdog_fault: bool        # → TIA: watchdogFault

class H2Interface(BaseModel):
    control: H2InterfaceControl
    plc_to_robot: H2InterfacePlcToRobot
    robot_to_plc: H2InterfaceRobotToPlc
    safety: H2InterfaceSafety
    
    @property
    def node_ids(self) -> dict:
        """Rückgabe der OPC-UA NodeIds für alle Member."""
        return {
            'control.plc_heartbeat': 'ns=3;s="H2_Interface_DB"."iface"."control"."plcHeartbeat"',
            # ... weitere ...
        }
```

Jedes Member in `udt.py` hat einen entsprechenden Feldnamen in der TIA-UDT (Naming-Konvention: snake_case →
camelCase).

### 2. Handshake-Logik (`src/h2_loader/plc/handshake.py`)

Die `H2HandshakeClient`-Klasse verwaltet den Auftrag-Handshake:

- Erkennt Flanken-Wechsel in `jobReqToggle`
- Prüft Preconditions (`operatingMode == 2`, `robotAlive`, etc.)
- Setzt `jobAckToggle` und `jobDoneToggle` (Flanken)
- Überwacht `jobIdEcho` und `jobResult`
- Loggt jeden Schritt für Fehlersuche

```python
class H2HandshakeClient:
    async def poll_and_update(self) -> None:
        """Pollt OPC UA, erkennt neue Aufträge via Flankenwechsel."""
        # Fetch aktuelle Werte
        iface = await self.opc_client.read_interface()
        
        # Hat sich jobReqToggle geändert?
        if iface.plc_to_robot.job_req_toggle != self._last_toggle:
            # Neue Flanke erkannt
            await self._handle_new_job(iface)
            self._last_toggle = iface.plc_to_robot.job_req_toggle
```

### Single Source of Truth: TIA-UDT

Die **TIA Portal UDT** (`tia/udt/H2_Interface_UDTs.scl`) ist die Quelle der Wahrheit:
- Feldnamen, Typen und Reihenfolge in der UDT sind verbindlich
- `udt.py` wird manuell abgeglichen (oder via Openness-Script automatisch extrahiert)
- `handshake.py` benutzt `udt.py` und abstrahiert die Ablauflogik darüber

Bei Änderungen an der UDT (neuer Member, Typ-Wechsel):
1. TIA-UDT ändern
2. `udt.py` aktualisieren
3. `handshake.py` ggf. anpassen
4. Tests laufen lassen

---

## Zusammenfassung

| Aspekt | Details |
|--------|---------|
| **Server** | Siemens S7-1500 (OPC UA integriert) |
| **Client** | Unitree H2 PLUS (Python asyncua auf Ubuntu 22.04) |
| **DB** | `H2_Interface_DB` mit Member `iface : H2Interface_UDT` |
| **Richtung Auftrag** | SPS → H2 (jobRequest, jobId, jobReqToggle) |
| **Richtung Antwort** | H2 → SPS (robotState, jobAckToggle, jobDoneToggle, jobResult) |
| **Sicherheit** | Hardwired Safety-Kreise, OPC UA ist funktional nur |
| **Handshake** | Toggle-Flanken, idempotent |
| **Polling** | H2 pollt regelmäßig (typisch 100 ms Zyklus), SPS lebt unabhängig |
| **Timeout** | Heartbeat-Überwachung ~3 Sekunden, bei Ausfall Notfall-Stop |

Der H2-Client ist untergeordnet und folgt der SPS; die SPS bleibt der Master der Automation und
Sicherheit.
