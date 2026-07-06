# PROJECT MEMORY — h2_loader

> **Append-only.** Neue Erkenntnisse/Entscheidungen werden **unten ergänzt**, nichts wird gelöscht
> oder überschrieben. Architektur-Entscheidungen zusätzlich als ADR unter `docs/adr/`.

## Projektüberblick

- **Ziel:** Unitree H2 PLUS (zweiarmig, 7 DoF/Arm) lädt/entlädt Werkstücke an einer feststehenden
  Induktionshärtemaschine. Ausbaustufe 2: Induktorwechsel (2 Schrauben).
- **Endeffektor:** einfacher pneumatischer Backengreifer (1 Zylinder, auf/zu).
- **Bewegung:** Teach-&-Replay über `unitree_sdk2_python` (kein ROS2 jetzt; ROS2/MoveIt2 nachrüstbar).
- **Zielsystem:** Ubuntu 22.04, CycloneDDS 0.10.2, MuJoCo-Sim teilt dieselbe DDS-Schnittstelle.
- **Tiefe v0.1:** Struktur + Interfaces + Stubs. Keine echte Roboterbewegung.

## Architektur-Eckpfeiler

1. Schichtentrennung `app → core → skills → {motion, hal, perception, plc}`; höhere Schichten kennen
   nur Interfaces. Konkrete Treiber nur im Composition Root `app.py`.
2. Drei Austauschpunkte: Motion-Backend (ADR-0003), Endeffektor + Ventil-Port (ADR-0002),
   Roboter-Treiber (Sim/SDK).
3. Skills = `precondition/execute/recover`, verdrahtet als py_trees-Behaviours im Orchestrator.

---

## Chronik

### 2026-06-29 — v0.1.0 — Initialgerüst angelegt

**Was:** Vollständiges Python-Paket `h2_loader` (src-Layout) mit Interfaces, Stubs, Config, Tests,
Doku erstellt. Komponenten:
- HAL: `Robot`/`Arm`, `EndEffectorInterface` + `PneumaticGripper`/`DexHand`, `ValveActuator`-Port
  (`H2IoValveActuator`/`PlcValveActuator`), `RobotDriverInterface` + `MujocoSimDriver`/`UnitreeSdkDriver`.
- Motion: `MotionPlannerInterface` + `TeachReplayPlanner` (aktiv) + `MoveIt2Planner` (Stub).
- PLC: `PlcInterface` + `OpcUaPlcClient` (Stub) + `Signal`-Enum.
- Perception: `PerceptionInterface` + `Camera`/`PoseEstimator` (Stubs).
- Skills: `LoadWorkpieceSkill`, `UnloadWorkpieceSkill`, `ChangeInductorSkill` (Zukunfts-Stub).
- Core: `Orchestrator` (py_trees + Fallback), `SkillBehaviour`-Adapter, `SafetyGate`.
- `app.py` als Composition Root mit CLI (`--driver sim|sdk`).

**Warum so:** Austauschbarkeit von Motion-Backend (ROS2-Umstieg) und Endeffektor ohne Skill-Änderung;
Sim-to-Real über gemeinsame DDS; Konfiguration statt Code.

**Entscheidungen:** ADR-0001 (Python-SDK statt ROS2), ADR-0002 (Pneumatikgreifer + Ventil-Port),
ADR-0003 (Motion-Backend-Interface).

**Umgebungs-Abweichung vom Ursprungsplan:** Umsetzung erfolgte in dieser Remote-Session **nicht** im
H2-Greenfield-Repo (`E:\Git\H2`, Remote `Tarr0k/H2plus`), sondern als selbst-enthaltenes
Unterverzeichnis `h2_loader/` im EMA-Engineering-Tools-Repo; Auslieferung per PR gegen dieses Repo.
Das im Ursprungsplan als „bestehend" referenzierte `unitree_h2_dokumentation.md` war in dieser
Umgebung nicht vorhanden; statt einer Rekonstruktion wurde der Ursprungsplan als
`docs/source_plan.md` abgelegt und dient als Kontextquelle. Verschieben nach `Tarr0k/H2plus` und
Git-Tag `v0.1.0` erfolgen lokal durch den Anwender.

**Branding:** Private-Modus bestätigt → kein EMA-Logo, kein Eigentums-Footer.

**Verifikation:** `pip install -e .` erfolgreich; `pytest` 11/11 grün; `python -m h2_loader.app
--driver sim` tickt die Lade-Sequenz erfolgreich durch (BT-Status SUCCESS) und terminiert sauber;
Architektur-Grep ohne Treiber-Importe in skills/core.

### 2026-06-29 — v0.1.0 — Repo nach Tarr0k/H2plus überführt

**Was:** Das in der Remote-Session erzeugte Gerüst wurde als eigenständiges Repo (Projekt auf
Repo-Wurzel, nicht als Unterverzeichnis) per Git-Bundle lokal übernommen und nach
`github.com/Tarr0k/H2plus` gepusht; Tag `v0.1.0` gesetzt. Damit lebt das Projekt nun wie geplant in
seinem eigenen Repo (nicht mehr im EMA-Tools-Repo).

**Warum:** Der Push aus der Remote-Web-Session scheiterte mit 403 — eine Websession hat nur
Schreibrecht auf ihr Start-Repo, nicht auf das fremde `Tarr0k/H2plus`. Übernahme daher lokal mit den
eigenen Credentials des Anwenders.

### 2026-06-29 — v0.1.1 — OPC-UA-UDT-Schnittstelle (Siemens SPS ↔ H2 PLUS)

**Was:** Strukturierte Schnittstelle zwischen S7-1500 (OPC-UA-Server) und H2 PLUS (Python-Client)
ergänzt — als TIA-Artefakt **und** Python-Spiegel:
- `tia/udt/H2_Interface_UDTs.scl` — 5 TYPE-Blöcke: `H2Interface_UDT` { `control`, `plcToRobot`,
  `robotToPlc`, `safety` }. Importierbar in TIA V20.
- `tia/README.md` — Import-/OPC-UA-Server-Anleitung.
- `docs/plc_interface.md` — Vollspezifikation (Topologie, UDT-Tabellen, Handshake-Sequenz,
  NodeId-Schema, Sicherheits-Abschnitt).
- `src/h2_loader/plc/udt.py` — Single Source of Truth: 41-Felder-Katalog + `node_id()` +
  IntEnums (JobRequest/RobotState/JobResult/OperatingMode).
- `src/h2_loader/plc/handshake.py` — `H2HandshakeClient` (In-Memory-Stub): Heartbeat, Toggle-basierter
  Auftrags-Handshake (poll/accept/finish), Anforderungs-Setter, SPS-Sim-Helfer für Tests.
- `config/plc.yaml` — `udt:`-Block (db_name `H2_Interface_DB`, ns 3, root `iface`); flaches
  `signals:`-Mapping unverändert erhalten.
- `tests/test_plc_interface.py` — 41 Tests (NodeId-Format, Feldkatalog, Enums, Heartbeat-Wrap,
  vollständiger Toggle-Zyklus).

**Warum so:** Toggle-/Edge-Handshake statt Impulse, weil OPC-UA pollt (nicht echtzeitfähig);
beidseitiger Heartbeat als Watchdog; gegenseitige Verriegelung über `robotInMachine`. **Sicherheit:**
OPC-UA ist NICHT sicherheitsgerichtet — echter Not-Halt/Bereichsfreigabe bleiben hardwired über die
Safety-SPS; die `safety`-Member sind nur funktionale Spiegel. Einziger Wahrheitsanker ist die
TIA-UDT; `udt.py` spiegelt sie, ein Konsistenz-Check stellt identische Membernamen sicher.

**Arbeitsweise:** Agent-Team parallel — `emaPLCCodeWriter` (SCL), `python-pro` (Python+Tests),
`technical-writer` (Doku); Integration zentral. Beim Merge ein Namens-Schnitzer korrigiert
(`H2_RobotInterface_UDT` → `H2Interface_UDT` in udt.py/handshake.py/plc.yaml).

**Branding:** Private-Modus → kein EMA-Logo, kein Eigentums-Footer.

**Verifikation:** `pytest` 45/45 grün; programmatischer Konsistenz-Check SCL-Member == Python-Feldkatalog
(7+13+16+5 = 41) OK. Tag `v0.1.1`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-29 — v0.2.0 — Job-Dispatch verdrahtet + PLC-Simulator

**Was:** Die OPC-UA-Handshake-Ebene (v0.1.1) ist jetzt in den Ablauf verdrahtet und ohne Hardware
end-to-end simulierbar:
- `core/job_runner.py` — `JobRunner.step()`: `tick_heartbeat → poll_job → (Safety) → accept_job →
  Skill-Dispatch nach `JobRequest` → finish_job(OK/NOK)`; `JobOutcome`-Dataclass; `run_until_idle()`.
  Robuste Pfade: Safety-Sperre → NOK, kein Skill → NOK, Skill-Exception/Fehlschlag → recover()+NOK,
  `set_robot_in_machine(True/False)` um die Ausführung (Try/Finally).
- `plc/plc_simulator.py` — `PlcSimulator` spielt die Maschinenseite über denselben Handshake:
  `set_machine_ready`, `tick_plc_heartbeat`, `send_job` (+ Seeding der Schritt-Ebene-Signale je
  Auftragsart), `acknowledge_done`, `run_cycle` (kompletter Zyklus in einem Aufruf).
- `app.py` — Sim-Pfad nutzt jetzt `H2HandshakeClient` + `JobRunner` + `PlcSimulator`
  (`sim.run_cycle(runner, JobRequest.LOAD, …)`); SDK-Pfad sendet keinen Auto-Auftrag (wartet auf reale
  SPS). `build_orchestrator` bleibt erhalten (nicht gelöscht).
- `util/config.py` — `PlcConfig.udt`-Feld; `tests/test_job_runner.py` (5 Tests: voller LOAD-Zyklus,
  kein Auftrag→None, unbekannter Auftrag→NOK, Vorbedingung-Fehlschlag→NOK, Heartbeat).

**Warum so:** `JobRunner` als eigene Ebene über den Skills trennt Auftragslogik (Maschine fordert an,
Roboter quittiert) sauber von der Skill-Mechanik. PLC-Sim teilt sich den Handshake-Store mit dem Runner,
sodass ein realistischer Zyklus ohne Hardware prüfbar ist.

**Bewusste Schuld / Folgeschritt:** Zwei PLC-„Stores" koexistieren — Job-Ebene über die UDT
(`H2HandshakeClient`), Schritt-Ebene noch über das flache `Signal`-Enum (`PlcInterface`). Das ist für
diesen Stand akzeptabel; ein späteres Inkrement sollte die Schritt-Ebene (Tür/Spannvorrichtung-Anforderungen
und -Zustände der Skills) ebenfalls auf die UDT-Member (`reqOpenClamp`, `doorOpen`, …) umstellen und das
flache `Signal`-Enum als Legacy entfernen oder kapseln.

**Branding:** Private-Modus → kein EMA-Logo, kein Eigentums-Footer.

**Verifikation:** `pytest` 50/50 grün; `python -m h2_loader.app --driver sim` fährt einen vollen
Job-Zyklus (Maschine fordert LOAD → H2 nimmt an → LoadWorkpieceSkill greift/legt ein → finish_job OK,
`JobOutcome(result=OK, skill_ran=True)`) und terminiert sauber. Tag `v0.2.0`, Push nach
`github.com/Tarr0k/H2plus`.

### 2026-06-29 — v0.3.0 — Locomotion-Layer (H2 ist mobil)

**KORREKTUR einer Grundannahme:** Der Ursprungsplan (`source_plan.md`, Phase 1) ging von einem auf
einer **feststehenden Plattform** stehenden Roboter aus. Das ist **falsch** — der H2 PLUS **muss sich
bewegen**: Rohteile aus dem Teilelager holen, zur Maschine bringen, Fertigteile in eine Kiste legen,
beim Werkzeugwechsel den Induktor aus einem Regal holen. Fortbewegung ist fester Bestandteil.
(Die *Maschine* steht weiterhin fest; nur die Annahme „Roboter steht" war falsch.)

**rl_gym evaluiert, verworfen als Standard:** `unitree_rl_gym` ist ein Trainings-Baukasten für
Lauf-Policies und unterstützt **H2 nicht** (nur Go2/G1/H1/H1_2 → Porting + Isaac Gym + RTX). Stattdessen
wird Unitrees **Onboard-Lauf-Regler (PC1) via SDK** kommandiert; rl_gym bleibt nur Fallback. → ADR-0004.

**Was:** Neue Locomotion-/Navigations-Ebene, konsequent hinter einem Interface:
- `hal/locomotion/base.py` — `LocomotionInterface` (`move_to(station)/current_station()/stop()`).
- `hal/locomotion/onboard_locomotion.py` — `OnboardLocomotion`-Stub (kommandiert auf dem Zielsystem den
  Onboard-Regler via SDK-High-Level-Wegpunkt; KeyError bei unbekannter Station).
- `config/stations.yaml` + `util/config.py` (`Station`/`StationsConfig`): benannte Stationen
  `home/part_storage/machine/dropoff_box/inductor_shelf` (Position [x,y,theta], am Zielsystem einmessen).
- `SkillContext.locomotion` (Pflichtfeld); Skills mehrstufig: *Laden* = laufe zu part_storage → greifen →
  laufe zu machine → einlegen; *Entladen* = machine → greifen → dropoff_box → ablegen; recover fährt home.
- `app.py`: `--stations-config`, `OnboardLocomotion` im Composition Root verdrahtet.
- `change_inductor`: Ablauf-Skizze um Lauf-Schritt (inductor_shelf) ergänzt (bleibt Zukunfts-Stub).
- Tests: `test_locomotion.py` (8) + conftest-Fixture `sim_locomotion`; `test_skills`/`test_job_runner`
  um `locomotion` erweitert.

**Offener Folgeschritt (wichtig):** **Sicherheit eines fahrenden Roboters** ist noch nicht gelöst
(Bereichsüberwachung, dynamische Hindernisse, Personenschutz). Eigene Ausbaustufe nötig. Außerdem weiter
offen: Schritt-Ebene auf UDT vereinheitlichen (aus v0.2.0).

**Branding:** Private-Modus → kein EMA-Logo, kein Eigentums-Footer.

**Verifikation:** `pytest` 58/58 grün; `python -m h2_loader.app --driver sim` fährt den vollen
Job-Zyklus inkl. Lauf-Schritten (part_storage → machine) durch (`result=OK`). Tag `v0.3.0`, Push nach
`github.com/Tarr0k/H2plus`.

### 2026-06-29 — v0.4.0 — Funktionaler Sicherheits-Supervisor (fahrender Roboter)

**⚠️ Grundsatz (verbindlich):** Diese Software ist **NICHT sicherheitsgerichtet**. Funktionale
Sicherheit/Personenschutz ist **hardwired und zertifiziert** (Safety-SPS mit F-Signalen, sichere
Laserscanner/Lichtgitter), ausgelegt nach Risikobeurteilung (ISO 12100) + ISO 10218 / ISO 3691-4 /
ISO 13849 / IEC 62061 / EN ISO 13855. Der `SafetySupervisor` ist nur ein **funktionaler Überwacher**.

**Betriebsart:** getrennt/abgesichert (separated) — Person im Bereich während Bewegung → sicherer Halt,
keine Ko-Präsenz. (Anwender-Entscheidung.)

**Was:**
- `core/safety.py` — `SafetySupervisor(SafetyGate)`: `is_clear()` (NOT-AUS + UDT-Safety-Member
  estopFromPlc/estopFromRobot/robotEnable/watchdogFault), `allow_move_to(station)` (Zone freigegeben +
  nicht belegt), `speed_limit(station)`, `set_zone_occupied()`, `evaluate_heartbeat()` (funktionaler
  Watchdog auf plcHeartbeat). `SafetyGate` unverändert (Backward-Compat).
- `config/safety_zones.yaml` + `util/config.py` (`SafetyZone`/`SafetyConfig`): 5 Zonen
  (transit/machine_zone/storage_zone/dropoff_zone/shelf_zone) mit Geschwindigkeitslimit + station_zone-Map.
- `hal/locomotion/safety_monitored.py` — `SafetyMonitoredLocomotion`: Wrapper, der vor jeder Fahrt
  `supervisor.allow_move_to()` prüft (Komposition, lässt OnboardLocomotion sauber).
- `plc/plc_simulator.py` — `set_machine_ready()` setzt zusätzlich robotEnable/safeZoneClear/watchdogFault.
- `app.py` — `--safety-config`, Supervisor + SafetyMonitoredLocomotion verdrahtet, JobRunner nutzt Supervisor.
- `docs/safety_concept.md` + `docs/adr/0005-sicherheitskonzept.md`; `tests/test_safety.py` (20 Tests).

**Warum so:** Supervisor erweitert das Gate (JobRunner unverändert nutzbar); Locomotion-Wrapper per
Komposition; Zonen rein konfigurativ. Hardwired/funktional-Grenze überall explizit.

**Offene Folgeschritte:** echte Sicherheitstechnik (zertifizierte Sensorik + Safety-SPS) + Risikobeurteilung
nach ISO 12100 + Performance-Level-Festlegung (extern, vor Inbetriebnahme zwingend); Sturz-/Stabilitäts-
sicherung des Humanoiden liegt bei Unitrees PC1-Regler; weiterhin offen: Schritt-Ebene auf UDT vereinheitlichen.

**Branding:** Private-Modus → kein EMA-Logo, kein Eigentums-Footer.

**Verifikation:** `pytest` 78/78 grün; Sperr-Nachweis (kein robotEnable / Zone belegt / Not-Halt /
unbekannte Station → blockiert, speed 0.0); `python -m h2_loader.app --driver sim` läuft bei Freigabe
weiter (`result=OK`). Tag `v0.4.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-29 — v0.5.0 — SDK-Grounding an den echten Unitree-Beispielen

**Was:** Die echten SDK-Beispiele (`github.com/unitreerobotics/unitree_sdk2_python`, `example/h2/…`, per
GitHub-API geprüft) ausgewertet und die Stubs/Doku daran geerdet:
- `docs/sdk_reference.md` (neu): reale API-Namen/Muster — `LocoClient`
  (`Init/Start/StandUp/Move/SetVelocity/StopMove`), `ChannelFactoryInitialize`, **`unitree_hg`**-IDL
  (`LowCmd_/LowState_`, NICHT `unitree_go`), `H2JointIndex` (29 Achsen), CRC + `RecurrentThread`,
  FSM `Start→StandUp`, `arm_sdk`; relevante Org-Repos inkl. Lokalisierungs-Bausteine.
- `OnboardLocomotion` + `UnitreeSdkDriver`: Docstrings ehrlich gemacht (echte Klassen/Methoden,
  Sim-vs-Real `ChannelFactoryInitialize(1,"lo")`/`(0,"enp3s0")`).
- ADR-0004: Nachtrag.

**Zentrale Korrektur:** Der Onboard-`LocoClient` ist **velocity-/FSM-basiert** und bietet **KEIN
Wegpunkt-Fahren**. `move_to(station)` bleibt als Interface gültig, braucht aber on-target zusätzlich eine
**Lokalisierungs- + Pfad-/Regelschicht** (`unilidar_sdk2`+`point_lio_unilidar` oder `unitree_ros2`+Nav2).
`OnboardLocomotion` ist bis dahin ein Platzhalter ohne autonome Navigation.

**Branding:** Private-Modus. **Verifikation:** nur Doku/Docstrings geändert; `pytest` 78/78 weiterhin grün.
Tag `v0.5.0`, Push nach `github.com/Tarr0k/H2plus`.

**Nächster geplanter Schritt:** Schritt-Ebene der Skills auf die UDT vereinheitlichen (flaches
`Signal`-Enum ablösen) — vom Anwender als nächster Schritt nach diesem Grounding gewählt.

### 2026-06-29 — v0.5.1 — Korrekturen aus der offiziellen H2-Doku

**Quelle:** offizielle H2-Doku (`support.unitree.com`, WAF-geschützt → via Browser-Extension extrahiert,
abgelegt unter `docs/unitree_docs/Unitree_H2_Zusammenfassung.md`).

**Korrekturen (wichtig):**
1. **Kein Modell „H2 Plus".** Unitree: H1/G1/**H2**/R1/G1-D; H2 in Varianten **H2** und **H2 EDU**.
   „H2plus" ist nur unser Repo-/Projektname; Produkt korrekt = **Unitree H2 (EDU)**.
2. **Secondary Development braucht die H2 EDU** — Standard-H2 erlaubt keine Eigenentwicklung; SDK-Zugang +
   Dexterous Hand sind EDU-exklusiv. Unser gesamter SDK-Ansatz setzt eine **H2 EDU** voraus
   (Beschaffungs-/Machbarkeitsfaktor; Pneumatikgreifer davon unabhängig).
3. **Onboard-Compute korrigiert:** PC1 Intel **i5** (Motion-Control, gesperrt) + optional PC2/3/4 i7 bzw.
   **Jetson Thor** (EDU). Die früher (v0.1.1-Tabelle) genannte „Blackwell-GPU/128 GB" stammte aus einer
   **unzuverlässigen Produktseiten-Abfrage** (mit halluziniertem EMA-Footer) und ist nicht belegt — als
   historischer Eintrag stehen gelassen (append-only), hier richtiggestellt.
4. **Debug-Modus Pflicht** für SDK-Steuerung (Fernbedienung L2+R2 / L2+A / L2+B), sonst Konflikt mit dem
   auto-startenden Motion-Control (Zittern). PR/AB-Steuermodi für Knöchel/Taille. DDS-Topics rt/lowcmd,
   rt/lowstate; IDL LowCmd_/LowState_/IMUState_/MotorCmd_/MotorState_.

**Eingearbeitet in:** `docs/sdk_reference.md` (Korrektur-Abschnitt) + `unitree_sdk_driver.py`-Docstring
(Debug-Modus, EDU, Topics). **Verifikation:** nur Doku/Docstrings; `pytest` 78/78 weiterhin grün.
Tag `v0.5.1`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-30 — v0.6.0 — Schritt-Ebene auf UDT vereinheitlicht (löst v0.2.0-Schuld)

**Was:** Die in v0.2.0 dokumentierte Schuld „zwei PLC-Stores" ist behoben. Die Schritt-Ebene der Skills
läuft jetzt ebenfalls über die UDT (`H2HandshakeClient`) — via neuer Fassade `plc/machine_io.py` `MachineIo`:
- Semantische API: `door_open()/fixture_free()/cycle_done()/clamp_open()/clamp_closed()/machine_ready()/…`,
  Anforderungen `request_open_clamp()/request_close_clamp()/request_open_door()/…`,
  `wait_clamp_closed()/wait_door_open()/…`, `set_gripper_holds()/set_current_step()`.
- `PlcSimulator`: kein `plc`-Param mehr; `send_job` setzt UDT-Maschinenzustand je Auftragsart;
  neues `service_requests()` reagiert flankenartig auf Roboter-Anforderungen (Clamp/Tür). `MachineIo`-
  Responder ruft das im Stub synchron auf (auf Zielsystem: OPC-UA-Polling).
- `SkillContext.plc` → `machine: MachineIo`. Skills (load/unload) komplett auf `MachineIo` umgestellt;
  redundantes `ROBOT_DONE`-Schreiben entfernt (Job-Abschluss macht `JobRunner.finish_job`).
- Flaches `Signal`/`PlcInterface`/`OpcUaPlcClient` als **Legacy** markiert (nicht gelöscht, von Skills
  ungenutzt). `app.py`: OpcUaPlcClient/Signal-Wiring entfernt; `MachineIo(handshake, responder=sim.service_requests)`.
- Tests: `conftest` MockPlc/mock_plc → neues `plc_env`-Fixture; `test_skills`/`test_job_runner` auf `machine`;
  neu `test_machine_io.py` (16). ADR-0006.

**Warum so:** ein einziger Wahrheits-Store (UDT) für Job- UND Schritt-Ebene; kohärenter Maschinen-Handshake
(Tür/Spannvorrichtung) in Sim testbar; näher an der echten OPC-UA-Anbindung (node_id-Mapping).

**Verbleibende offene Punkte:** echter `asyncua`-Client fürs Zielsystem; `MachineIo.wait_*` ist im Stub
nicht-blockierend (Responder-Muster) → echtes Polling/Subscription on-target; Induktorwechsel-Ausbau;
Lokalisierungs-/Pfadschicht für `move_to(station)` (siehe v0.5.0).

**Branding:** Private-Modus. **Verifikation:** `pytest` 96/96 grün; Architektur-Check (skills/ ohne
Legacy-Importe) OK; `python -m h2_loader.app --driver sim` fährt vollen LOAD-Zyklus inkl. UDT-Clamp-
Handshake (`request_close_clamp → service_requests → clampClosed → wait_clamp_closed`) → `result=OK`.
Tag `v0.6.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-30 — v0.7.0 — GR00T-Zielarchitektur dokumentiert (Endziel)

**Was:** Das vom Anwender gesetzte Endziel „NVIDIA Isaac GR00T als Steuerungs-Policy" als Zielarchitektur
festgehalten (Doku-only, KEIN Code): `docs/roadmap_groot.md` + `docs/adr/0007-groot-policy-backend-zielarchitektur.md`.

**Verifizierte Fakten (aus github.com/NVIDIA/Isaac-GR00T, API-geprüft 2026-06-30):**
- Modell **GR00T N1.7**, ~3B Parameter, **Apache-2.0**, Basis-Checkpoint `nvidia/GR00T-N1.7-3B` (VLA).
- **Embodiment:** Unitree **G1 ist unterstützt** (REAL_G1 / UNITREE_G1), **H2 NICHT** → H2 läuft als
  **`NEW_EMBODIMENT`** (eigenes Fine-Tuning, eigene URDF/Modality-Config). Wichtige Einordnung.
- Daten: GR00T-flavored **LeRobot v2**. Hardware: Inferenz min 16 GB; **AGX Thor 128 GB ~10,7 Hz (TensorRT)**
  = robot-mounted Deployment (passt auf H2 EDU + Thor). Fine-Tune min 40 GB, empf. 4–8× H100/L40.
- Toolchain: `xr_teleoperate` → LeRobot v2 → Fine-Tune (`examples/finetune.sh`) → Sim (`unitree_sim_isaaclab`)
  → Deploy (TensorRT/Thor).

**Integrations-Seam (nur dokumentiert, nicht gebaut):** künftiges `PolicyInterface` hinter der Skill-Ebene
mit Backends `ScriptedPolicy` (heutiges Teach-in = Vorlage `TeachReplayPlanner`, bleibt Fallback) und
`GrootPolicy`. Orchestrator/JobRunner/SafetySupervisor/MachineIo/Locomotion bleiben unverändert. Gelernte
Policy ist nicht-deterministisch → Safety-Clamping + hardwired Safety + SafetySupervisor zwingend.

**Hinweis zur Sorgfalt:** Der schreibende Agent hatte zunächst Zahlen/Termine erfunden (50–100k Demos,
24–72 h, Quartals-Daten, „ScriptedPolicy implementiert") — diese wurden vor dem Commit entfernt/ehrlich
gemacht (Grep-Check sauber). GR00T-Spezifika bleiben „gegen aktuelle NVIDIA-Doku prüfen".

**Branding:** Private-Modus. **Verifikation:** nur Doku; `pytest` 96/96 weiterhin grün. Tag `v0.7.0`,
Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-30 — v0.7.1 — Setup-Anleitung `docs/dev_environment.md`

**Was:** Entwicklungsumgebung in drei Stufen dokumentiert: A) dieses Projekt (Stub/Sim) — Windows **oder**
Linux, nur Python 3.10+ + `pip install -e .[dev]`, kein GPU/Roboter; B) echter H2-Betrieb — Ubuntu 22.04,
CycloneDDS 0.10.2, unitree_sdk2(_python), H2 **EDU** + Debug-Modus; C) GR00T — Trainings-GPU (≥40 GB) +
Jetson Thor zum Deploy, CUDA 12.6+, Isaac-GR00T/LeRobot/Isaac Lab. Plus „Was läuft wo"-Matrix.
**Verifikation:** nur Doku; `pytest` 96/96 grün. Tag `v0.7.1`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-30 — v0.8.0 — Policy-Seam (ADR-0007 operationalisiert)

**Was:** Der austauschbare Manipulations-Policy-Seam aus ADR-0007 ist gebaut — neues Paket `policy/`:
- `base.py`: `Observation`/`Action`/`PolicyInterface` (`predict(Observation)→Action`).
- `scripted_policy.py`: `ScriptedPolicy` (name="scripted") — heutiges Teach-in als deterministische Policy
  (lädt angelernte Posen).
- `groot_policy.py`: `GrootPolicy` (name="groot") — **Stub**, `predict` wirft NotImplementedError mit
  Roadmap-Verweis (GR00T N1.7, NEW_EMBODIMENT, Jetson Thor); KEINE Inferenz.
- `safeguard.py`: `SafeguardedPolicy` — clampt Gelenkziele auf `joint_limits` (Defense-in-Depth; ausdrücklich
  KEIN funktionaler Sicherheitsersatz — hardwired Safety + SafetySupervisor bleiben).
- `fallback.py`: `FallbackPolicy` — primary-Fehler → fallback (groot→scripted).
- `SkillContext.policy` (optional); Skills nutzen `_reach()` → Policy wenn gesetzt, sonst bisheriger
  motion-Pfad (bestehende Tests bleiben grün). `app.py --policy scripted|groot`, `build_policy()`.

**Warum so:** macht alle Manipulations-Policies austauschbar (Teach-in heute, GR00T später) ohne Änderung an
Orchestrator/JobRunner/SafetySupervisor/MachineIo/Locomotion — der Architektur-Payoff Richtung Endziel GR00T.

**Verifikation:** `pytest` 111/111 grün (96+15); `--driver sim` → `Policy: safe:scripted` → result=OK;
`--driver sim --policy groot` → `Policy: safe:fallback`, GrootPolicy-Stub wirft → Fallback auf scripted →
result=OK. Branding: Private-Modus. Tag `v0.8.0`, Push nach `github.com/Tarr0k/H2plus`.

**Offen Richtung GR00T (nicht von hier delegierbar — braucht Hardware/Daten):** Stufe 1 Teleop-Daten,
Stufe 2 Fine-Tuning NEW_EMBODIMENT, Stufe 3 Thor-Deployment + reale GR00T-Inferenz in `GrootPolicy`.
Weiter sim-machbar: Induktorwechsel-Ausbau, Lokalisierungs-/Pfadschicht für `move_to`, asyncua-Client (Code).

### 2026-06-30 — v0.9.0 — Lokalisierungs-/Pfadschicht für move_to (Closed-Loop)

**Was:** Die v0.5.0-Lücke geschlossen — `move_to(station)` ist jetzt ein velocity-basierter Closed-Loop
(der echte LocoClient kann kein Wegpunkt-Fahren). Neue Dateien in `hal/locomotion/`:
- `localization.py`: `Pose2D`, `LocalizationInterface`, `SimLocalization` (kinematische Body-Frame-Integration
  `integrate(vx,vy,omega,dt)`, `wrap_angle`). Ziel: LiDAR-Odometrie (`unilidar_sdk2`+`point_lio_unilidar`).
- `velocity_sink.py`: `VelocitySink`, `SimVelocitySink` (integriert SimLocalization), `LocoClientVelocitySink`
  (Stub → `LocoClient.Move/StopMove` am Zielsystem).
- `navigating_locomotion.py`: `NavigatingLocomotion` (LocomotionInterface) — P-Regler im Body-Frame
  (Lagefehler→`Move(vx,vy,omega)`), Clamping (max_linear/angular), Toleranz (tol_xy/tol_theta), max_steps-Guard.
- `config/stations.yaml` `nav:`-Block + `StationsConfig.nav`.
- `app.py` Sim-Pfad: NavigatingLocomotion + SimLocalization(start=home) + SimVelocitySink, weiter in
  `SafetyMonitoredLocomotion` gewrappt. SDK-Pfad: OnboardLocomotion-Stub bleibt.
- `tests/test_navigation.py` (25). `OnboardLocomotion` bleibt als einfacher Backend erhalten.

**Ehrlichkeit:** Sim = perfekte Lokalisierung + kinematische Integration; KEINE Hindernisvermeidung;
holonomisches Modell (am Zielsystem zu verifizieren). Skills/Orchestrator/Safety unverändert (nur neuer
Locomotion-Backend hinter dem Interface).

**Verifikation:** `pytest` 136/136 grün (111+25); Dry-Run fährt Stationen per Closed-Loop an
(part_storage erreicht @ (1.959,0.978,1.569) ≈ Ziel (2,1,1.57)), `result=OK`. Privat-Modus.
Tag `v0.9.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-30 — v0.10.0 — Induktorwechsel-Ausbau (3. Kernaufgabe komplett)

**Was:** Induktorwechsel (Führung mit 2 Schrauben) implementiert — nutzt die Endeffektor-Abstraktion für
**Werkzeugwechsel** (1-Zylinder-Greifer kann keine Schrauben lösen):
- `hal/end_effector/screwdriver.py`: `ScrewdriverEndEffector` (grasp/release/is_holding + `loosen()`/`tighten()`).
- `hal/tool_changer.py`: `ToolChanger` (real = ATI-QC-Dock, Stub = direkter Tausch): `equip(arm, tool)`,
  `current_tool`; `Arm.set_end_effector()` ergänzt.
- `skills/change_inductor.py`: voll implementiert, 10 Schritte, einarmig mit Tool-Change
  (Maschine → Tür → Schrauber → 2 lösen → Greifer → alten Induktor raus → Regal alt ablegen/neu holen →
  einsetzen → Schrauber → 2 anziehen → Greifer). isinstance-Prüfung, recover, Schrittzähler.
  Alternative zweiarmig im Docstring vermerkt.
- `_reach()` in `SkillInterface`-Basis hochgezogen (load/unload/change teilen ihn).
- `SkillContext.tool_changer` (optional); JobRunner-Dispatch um `JobRequest.CHANGE_INDUCTOR`;
  `PlcSimulator.send_job` CHANGE_INDUCTOR-Seeding; `app.py --job load|unload|change_inductor`.
- 4 neue Posen-YAMLs (inductor_screw_1/2, inductor_pick, inductor_place). `tests/test_change_inductor.py` (21).

**Damit alle 3 Kernaufgaben sim-vollständig:** Laden, Entladen, Induktorwechsel.

**Verifikation:** `pytest` 157/157 grün (136+21); `--job change_inductor` fährt vollen Zyklus
(Tool-Change gripper↔screwdriver 2×, loosen 2×, tighten 2×) → `result=OK`; LOAD weiterhin OK. Privat-Modus.
Tag `v0.10.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-06-30 — v0.11.0 — Echter asyncua-OPC-UA-Client (cross-platform, lokal verifiziert)

**Was:** OPC-UA-Transport via `asyncua` — letzter rein softwareseitiger Baustein. Cross-platform (Windows!),
end-to-end ohne echte SPS testbar (asyncua bringt eigenen Server mit).
- `plc/transport.py`: `HandshakeTransport`-ABC (connect/disconnect/read/write).
- `plc/asyncua_transport.py`: `AsyncuaTransport` (`asyncua.sync.Client`, Lazy-Import in connect(),
  NodeId via `udt.node_id` = `ns=3;s="H2_Interface_DB"."iface"."<section>"."<member>"`, ua-Typen aus dem
  Feldkatalog: Bool→Boolean/Int→Int16/UInt→UInt16/DInt→Int32, DataValue+Variant-Write).
- `H2HandshakeClient.__init__(transport=None)`: mit Transport delegieren read/write/connect/disconnect an
  OPC-UA; ohne Transport unverändert In-Memory. **High-Level-Methoden (poll_job/accept_job/finish_job/…)
  unverändert → laufen transparent über OPC-UA.**
- `pyproject.toml` `[plc]` += `asyncua>=2.0`. `tests/test_asyncua_transport.py` (5, `importorskip`):
  lokaler `asyncua.sync.Server` spiegelt die UDT-NodeIds → echter Lese-/Schreib-Roundtrip + voller
  Toggle-Handshake über OPC-UA.

**Wichtig (Umgebung):** asyncua läuft auf **Windows** — KEIN Ubuntu/SPS für die Verifikation nötig.
Unter **Python 3.14** ist **asyncua 2.0.1** erforderlich (1.1.x hat `issubclass()`-Bug in ua_binary.py).
Nur der finale Test gegen die **reale S7-1500** braucht die Hardware.

**Verifikation:** ohne asyncua `pytest` 157 passed + 1 skipped; mit asyncua 2.0.1 **162/162 grün**
(5 echte OPC-UA-Loopback-Tests). Privat-Modus. Tag `v0.11.0`, Push nach `github.com/Tarr0k/H2plus`.

**Damit sind alle rein softwareseitigen Bausteine erledigt.** Verbleibend nur Hardware/Daten/extern:
GR00T Stufe 1–3 (H2 EDU, Teleop-Daten, GPUs, Jetson Thor), reale SPS-/Roboter-Inbetriebnahme,
zertifizierte Sicherheitstechnik + ISO-12100-Risikobeurteilung.

### 2026-07-03 — v0.12.0 — GR00T-Vorbereitung (ohne Hardware nutzbare Artefakte)

**Was:** GR00T-seitige Vorbereitung, die schon jetzt ohne EDU/GPU/Ubuntu möglich ist (GR00T selbst läuft
nur auf Linux+CUDA):
- `groot/` (TOP-LEVEL, außerhalb `src/`, importiert gr00t → NICHT von der Testsuite importiert):
  `h2_modality_config.py` (H2-NEW_EMBODIMENT-Modality-Config nach SO100-Muster: video head/wrist,
  state/action right_arm+gripper, language; register_modality_config), `meta_modality.example.json`, `README.md`.
- `src/h2_loader/dataset/lerobot_export.py`: `LerobotDatasetExporter` (start_episode/add_step/end_episode/
  finalize) schreibt GR00T-flavored LeRobot-v2-Layout (data/chunk-000/episode_N.jsonl + meta/modality|info|
  episodes|tasks); Parquet nur wenn pyarrow da (kein Pflicht-Dep), sonst JSONL. Videos = Platzhalter (Rig).
- `policy/groot_policy.py`: Adapter fertig — `H2_RIGHT_ARM_JOINTS` (22–28), `_observation_to_groot` /
  `_groot_action_to_action` (7[+1 Greifer], Schwelle 0.5, Längenprüfung); `predict()` baut Mapping und wirft
  weiter NotImplementedError (Inferenz nur auf Rig). 
- `docs/groot_setup.md`: Anforderungen (CUDA/Python-Matrix, GPU-Tiers, uv sync/FFmpeg/flash-attn/TensorRT,
  Triton-Patch CUDA13) + H2-NEW_EMBODIMENT-Workflow + Safety-Hinweis.

**GR00T-Anforderungen (verifiziert, README/hardware_recommendation.md):** Linux; dGPU CUDA 12.8/Py3.10,
Jetson Thor CUDA 13.0/Py3.12; Inferenz ≥16 GB VRAM (AGX Thor ~10,7 Hz TensorRT), Fine-Tune ≥40 GB
(empf. H100/L40); LeRobot v2 + modality.json; Apache-2.0. Läuft NICHT auf dem Windows-Dev-Rechner.

**Nächster echter Schritt braucht Hardware:** Ubuntu+GPU-Rig (`uv sync` → gr00t), H2 EDU + `xr_teleoperate`
für Teleop-Daten → Exporter → Fine-Tune NEW_EMBODIMENT → Sim-Val → Thor-Deploy → GrootPolicy-Inferenz ergänzen.

**Verifikation:** `pytest` 174/174 grün (162+12); `groot/` nicht von der Suite importiert. Privat-Modus.
Tag `v0.12.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-03 — v0.13.0 — Hardware-Bring-up + Digital-Twin-Anbindung

**Was:** Damit der H2 EDU „schnell lebt" — gestufter, sicherheits-gegateter Bring-up + reale SDK-Adapter
(hardware-untested, SDK-treu nach den Beispielen, lazy import → Suite bleibt grün ohne SDK):
- `hal/h2_joint_index.py`: `H2JointIndex` (29 Achsen; LEFT_ARM 15–21, RIGHT_ARM 22–28), reine Konstanten.
- `hal/drivers/unitree_sdk_driver.py` REAL ausimplementiert: lazy `ChannelFactoryInitialize`, unitree_hg
  `LowCmd_/LowState_`, `CRC`, Subscriber rt/lowstate, Publisher rt/lowcmd; `send_joints` **gesperrt** solange
  `enable_commanding=False` (RuntimeError); konservative kp/kd; arm_sdk-Gewicht als Best-Effort („nicht
  verifiziert"). Sicherheits-Docstring (Debug-Modus Pflicht, H2 EDU).
- `hal/locomotion/velocity_sink.py`: `LocoClientVelocitySink` real (LocoClient connect/bring_up
  Damp→Start→StandUp/Move/StopMove), lazy; `SimVelocitySink` unverändert.
- `bringup.py`: `BringupSequencer` (Phasen 0 Netz/Debug → 1 DDS+LowState → 2 Loco-FSM → 3 Arm-Home
  (nur `--enable-commanding`) → 4 OPC-UA-Handshake), injizierbare Komponenten (mock-testbar), CLI
  `python -m h2_loader.bringup` / Console-Script `h2-bringup`.
- `config/robot.real.yaml` (enp3s0/domain 0) + `config/robot.sim_mujoco.yaml` (lo/domain 1).
- `docs/bringup.md` (Checkliste inkl. Digital-Twin-Abschnitt), Tests: test_h2_joint_index, test_bringup
  (nur Mocks), test_hardware_smoke (importorskip + H2_HARDWARE=1 → bei uns SKIPPED).

**Digital Twin (unitree_mujoco):** stellt dieselbe DDS-Schnittstelle wie der echte H2 bereit → unsere realen
Adapter laufen unverändert dagegen (domain 1 / `lo`). Erlaubt physikalische Vorab-Validierung OHNE echten
Roboter/GPU — aber **nur Linux** (Unitree-Stack). Der reine Logik-Stub (`--driver sim`) läuft auch auf Windows.

**Ehrlichkeit:** SDK-naher Code hier nicht ausführbar/verifiziert (kein SDK/Roboter/Windows) — am ersten
Reallauf prüfen; Doku-Embellishments des Agenten korrigiert (Quadruped-Gelenknamen, nicht existente
CLI-Flags, falscher Doc-Verweis).

**Verifikation:** `pytest` 195 passed, 1 skipped (Hardware-Smoke); Import ohne SDK ok (lazy); CLI-Hilfe ok.
Privat-Modus. Tag `v0.13.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-03 — v0.13.1 — unitree_mujoco-Twin: konkrete Setup-Befehle in bringup.md

**Was:** Digital-Twin-Abschnitt in `docs/bringup.md` um die realen Setup-Schritte erweitert (C++- und
Python-Variante, `-r h2`). Verifizierte Fakten aus `unitreerobotics/unitree_mujoco` (per API):
- **H2-Modell ist enthalten** (`unitree_robots/h2`; neben a2/b2/g1/go2/h1/h1_2/r1) — kein eigenes MJCF nötig.
- MuJoCo = **CPU-Physik, KEINE RTX-GPU** (nur Isaac Sim/GR00T braucht GPU). Ubuntu 20.04/22.04, normaler
  x86_64-PC, ~8–16 GB RAM, iGPU/OpenGL für Viewer. Im Grunde Stufe B + MuJoCo.
- C++: `apt libyaml-cpp-dev libspdlog-dev libboost-all-dev libglfw3-dev`; unitree_sdk2 → /opt/unitree_robotics;
  MuJoCo-Release (z. B. 3.3.6) → ~/.mujoco + symlink; `cmake .. && make`; `./unitree_mujoco -r h2 -s scene_terrain.xml`.
- Python: `pip3 install -e unitree_sdk2_python` (CycloneDDS) + `pip3 install mujoco pygame`; `config.py` ROBOT="h2";
  `python3 simulate_python/unitree_mujoco.py`.
- Gegen den Twin: `python -m h2_loader.bringup --iface lo` (domain 1) / `config/robot.sim_mujoco.yaml`.

**Verifikation:** nur Doku; `pytest` 195/1skip unverändert. Tag `v0.13.1`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-03 — v0.14.0 — Ubuntu-Twin-Setup-Skript

**Was:** `scripts/setup_ubuntu_twin.sh` — idempotentes, non-interaktiv ausführbares Installationsskript für
den kompletten `unitree_mujoco`-Digital-Twin-Stack auf Ubuntu: apt-Deps → CycloneDDS 0.10.2 →
unitree_sdk2 (/opt/unitree_robotics) → unitree_sdk2_python → MuJoCo-Release (~/.mujoco) →
unitree_mujoco (C++-Build) → h2plus-Klon + venv + `pip install -e .[plc]` + pytest. Konfigurierbar per
Env (MUJOCO_VERSION/WORKDIR/…), `--yes` für non-interaktiv, `sudo -n` (NOPASSWD Pflicht für SSH-Lauf),
Verifikations- + „Nächste Schritte"-Ausgabe. Bash-Syntax lokal geprüft (`bash -n`). In `docs/bringup.md`
als empfohlener Weg verlinkt.

**Kontext:** Anwender erwägt, mir per **SSH** Zugang zum Ubuntu-Rechner zu geben, damit ich alles dort
installiere. Sauberer Weg = dieses reproduzierbare Skript ausführen (einsehbar/auditierbar) statt Ad-hoc.
Voraussetzungen für SSH-Lauf: key-basiertes SSH (Passwort-Prompts hängen den non-interaktiven Bash),
`sudo` NOPASSWD, Internet. MuJoCo-Viewer ist GUI (Display); headless nur Bring-up Phase 1.
**Am Ziel-Ubuntu ungetestet** (hier nur Syntax-Check) — beim ersten Lauf verifizieren.

**Verifikation:** `bash -n` grün; `pytest` (Windows-Dev) 195/1skip unverändert. Tag `v0.14.0`,
Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-06 — v0.15.0 — Twin-Deployment auf `ematalos` (real) + VNC-Viewer über Tailscale

**Was:** Der komplette Twin-Stack wurde per SSH (über Tailscale) auf dem realen Ubuntu-Rechner **`ematalos`**
(Tailscale 100.68.27.117, User `ema`) installiert und der **H2 ist im MuJoCo-Viewer über VNC sichtbar**.
- Setup-Skripte hinzugefügt: `scripts/enable_ssh_sudo.sh` (Key + NOPASSWD-sudo), `scripts/setup_ubuntu_twin.sh`
  (Twin-Stack), **`scripts/setup_vnc_viewer.sh`** (TigerVNC :2 + openbox + **H2-MuJoCo-Viewer-Autostart** in
  `~/.config/tigervnc/xstartup`, ufw `allow in on tailscale0`).
- Installiert auf ematalos: CycloneDDS 0.10.5, unitree_sdk2→/opt/unitree_robotics, MuJoCo 3.10.0,
  unitree_mujoco (C++), Python 3.10.20-venv via `uv` (unitree_sdk2py+cyclonedds 0.10.2, mujoco, asyncua,
  h2_loader[plc]) → pytest 195/1skip. Umgebung: **Ubuntu 26.04, System-Python 3.14 (nicht nutzbar → uv-3.10),
  cmake 4/gcc 15 (→ `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`), GPU Quadro M4000 (zu alt für GR00T)**.
- VNC: Display :2 / Port 5902, Passwort `h2talos-view` (ändern!), Zugriff `100.68.27.117:5902`.
- **Wichtige Erkenntnis:** MuJoCo-Viewer öffnet KEIN Fenster über detachte SSH-Starts — nur aus der
  Desktop-Session (xstartup). Reines Visualisieren via `python -m mujoco.viewer --mjcf=…/h2/scene.xml`.

**Offen:** Voller DDS-Twin (h2_loader ↔ Sim) — Unitrees `simulate_python`-Bridge wirft bei H2 `IndexError`
(auf Quadrupeds ausgelegt, kommt mit 29 Gelenken nicht klar); muss gefixt werden. Der C++-`unitree_mujoco`
läuft, öffnet aber ebenfalls keinen eigenen Viewer über SSH.

**Verifikation:** H2-Viewer-Fenster „MuJoCo : Unitree H2" auf VNC :2 bestätigt; `bash -n` der Skripte grün;
`pytest` (Windows) 195/1skip unverändert. Tag `v0.15.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-06 — v0.16.0 — H2-Laufen-lernen: Gerüst auf G1-Basis (GPU-freie Vorbereitung)

**Vorlagen-Entscheidung (recherchiert):** Es existiert **KEINE fertige H2-Lauf-Policy** (Unitree-RL-Repos:
nur G1/H1/H1_2/Go2/A2). **G1_29dof ist die beste Vorlage** — H2 und g1_29dof haben **identische
Gelenknamen/-struktur** (verifiziert via gh api): Beine 12 (6/Bein, 2-DoF-Knöchel), Taille 3
(yaw/roll/pitch), Arme 14 (7/Seite). H1 schlechter (4-DoF-Arme ohne Handgelenk, 1-DoF-Taille, 10-DoF-Beine).
Gilt für **alles**: Locomotion (Beine), Manipulation/Arme, und GR00T (G1 ist dort unterstützte Embodiment;
H2=NEW_EMBODIMENT auf G1-Basis).

**Wichtige verifizierte Falle:** **Knöchel-Reihenfolge H2 vs. G1 vertauscht** — H2 = `…knee, ankle_roll,
ankle_pitch`, G1 = `…knee, ankle_pitch, ankle_roll`. In der Config berücksichtigt (default_angles umsortiert).

**Was:** neuer Top-Level-Ordner `training/` (nicht im Paket/Tests): `h2_locomotion_deploy.yaml` (aus
`unitree_rl_gym` g1.yaml adaptiert: num_actions 12, num_obs 47, kps/kds von G1 als Startwerte, xml→h2/scene,
50 Hz), `h2_joint_map.md` (12 Bein-DoF↔Aktionsindex + Knöchel-Falle + Arme/Taille=g1_29dof), `README.md`
(rl_lab/IsaacLab empfohlen; H2-Robot anlegen→Train RTX→ONNX→Twin-CPU-Deploy). `docs/locomotion_training.md`
(Strategieplan). **Gewichte NICHT übertragbar** (G1 1,3 m/35 kg vs H2 1,8 m/70 kg) → mit H2-URDF neu trainieren.

**Hardware:** Training braucht **RTX-GPU** (M4000 reicht nicht); Policy-Deploy (ONNX) läuft CPU im Twin.
Locomotion (RL, Beine) und Manipulation (GR00T/Teach-in, Arme) bleiben getrennte Policies.

**Verifikation:** `pytest` 195/1skip unverändert (training/ ohne Einfluss); Knöchel-Reihenfolge unabhängig
bestätigt. Tag `v0.16.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-06 — v0.17.0 — Experiment: G1-Policy direkt auf H2 im MuJoCo-Twin (GPU-frei)

**Frage des Anwenders:** „Können wir nicht die G1-Bewegungen nehmen und hochskalieren — wenn's
schiefgeht, warten wir auf die GPU?" → Ausprobiert (null GPU-Kosten, reine CPU-Inferenz).

**Was:** neues Skript `training/deploy/deploy_h2_g1policy.py`. Führt die vortrainierte G1-Policy
(`unitree_rl_gym/deploy/pre_train/g1/motion.pt`, TorchScript) auf dem **vollen H2-MJCF** (31 Aktuatoren)
aus — nur die 12 Beingelenke von der Policy geregelt, Taille/Arme/Kopf auf Startpose gehalten.
Obs-Konstruktion/Scales/Gait-Phase 1:1 aus Unitrees `deploy_mujoco.py` übernommen (obs=47, 50 Hz).
`--headless` (SSH-Diagnose mit Sturzerkennung) und Viewer-Modus mit **Auto-Reset bei Sturz**.

**Zwei verifizierte Fallen gelöst — namensbasiertes Mapping:** die 12 Beingelenke werden strikt in
G1-Reihenfolge über `mj_name2id`+`actuator_trnid`+`jnt_qposadr/jnt_dofadr` abgegriffen. Das löst
automatisch (a) den Knöchel-Swap (H2 ctrl-Index-Reihenfolge wird real `[0,1,2,3,5,4, 6,7,8,9,11,10]`)
UND (b) den Unterschied Aktuator-Reihenfolge (Beine,Taille,Arme,Kopf) vs. qpos-Gelenkreihenfolge
(Beine,Taille,Kopf,Arme) des vollen H2-Modells.

**Ergebnis (headless, reproduzierbar):** Policy läuft dimensional sofort, H2 macht echte Schritte.
kp_scale 1,0 → Sturz 0,47 s; 2,0 → 0,75 m/1,05 s; **3,0 (Optimum) → 0,86 m vorwärts, Sturz 1,47 s**;
4,0/5,0 schlechter. Stehen (vx=0) analog max ~1,5 s. **Fazit: „Hochskalieren" einer Policy geht nicht** —
H2 ~2× G1-Masse, trainierte Balance passt nicht → Sturz nach ~1,5 s; Gain-Anheben ist kein Fix
(Dynamik-/Policy-Mismatch, kein Gain-Problem). Bestätigt: **echtes Retraining auf RTX-GPU nötig.**
Nutzen: funktionierende Deploy-Pipeline (obs→Policy→PD→H2 im Twin) steht — die spätere echte
H2-Policy (`policy.onnx`) wird hier nur eingehängt.

**Betrieb:** CPU-Torch 2.12.1 in die uv-venv installiert (PyTorch-CPU-CDN `download-r2` hatte
TLS-HandshakeFailure → Default-PyPI-Wheel genommen, läuft auf CPU). Demo im VNC via umgebogener
`~/.config/tigervnc/xstartup` (Original gesichert als `xstartup.plainviewer.bak`), VNC :2 neu gestartet;
H2 läuft/kippt/resettet in Endlosschleife, GPU-gerendert (VirtualGL, M4000 ~19 %).

**Verifikation:** headless-Sweep wie oben; Demo-Prozess stabil im VNC. `pytest` unverändert
(training/ ohne Einfluss auf die Suite). Tag `v0.17.0`, Push nach `github.com/Tarr0k/H2plus`.

### 2026-07-06 — v0.18.0 — Modellbasierter Gehregler (kein ML) + ehrlicher Befund

**Auftrag des Anwenders:** Ohne GPU weiter Richtung „H2 laeuft" — gewaehlt: modellbasierter
Gehregler (rein kinematisch, CPU). Umsetzung ueber Agent-Team (`python-pro` schrieb Modul), danach
empirische Verifikation/Tuning durch mich im MuJoCo-Twin auf ematalos.

**Neu (`training/gait/` + Runner):**
- `leg_ik.py` — `LegIK`: Damped-Least-Squares-IK pro Bein via MuJoCo-Jacobi gegen interne Scratch-MjData.
  **Konvergiert exzellent (Residuum ~1e-6 m, Fuss flach 0°, 2-4 Iter).** Drei verifizierte Fallen gefixt:
  (1) `mj_comPos` noetig, sonst liefert `mj_jac` Nullmatrix; (2) Orientierungsfehler `mju_subQuat` ist
  im LOKALEN Frame → in Weltframe drehen; (3) **Kaltstart aus q=0 divergiert (Knie-Singularitaet)** →
  Default-Startschaetzung = leichte Kniebeuge `[-0.3,0,0,0.6,-0.3,0]` + dq-Clamping.
- `gait.py` — `QuasiStaticGait`/`GaitParams`: quasi-statischer Gang (Becken ueber Standfuss verlagern,
  Schwungfuss-Bogen). Params tunebar: pelvis_height 0.90, foot_lateral, step_length/height, cycle_time,
  ds_ratio, com_shift, **foot_x_offset 0.04** (Knoechel unter CoM).
- `balance.py` — `BalanceController`(ABC) + `AnkleStrategyBalance`: Knoechel-Sollwinkel aus Rumpfneigung.
- `walk_controller.py` — `WalkController`: Gait→pelvisrelative Fusszielposen→IK→12 Gelenkwinkel.
- `deploy/deploy_h2_walk.py` — Runner (Mapping/PD/headless/Viewer wie deploy_h2_g1policy.py).

**Ehrlicher Kernbefund (im Twin verifiziert):** Ein **positionsgeregelter H2 (72 kg, 29 DoF) ist ein
INSTABILES Gleichgewicht**. Selbst bei perfekter Standpose (CoM in Stuetzflaeche, Fuesse flach) kippt er
ohne Rueckkopplung nach ~1,7 s. Diagnose-Kette: CoM lag ~0,1 m VOR dem Knoechel-Pivot (→ foot_x_offset
loest das); dann kippt er in die andere Richtung → grundsaetzliche dynamische Instabilitaet. **Hoehere
Gains + steifere Knoechel machen es SCHLECHTER** (kein Kraftmangel; Aktuatoren sind unbegrenzte
Drehmoment-Motoren). Ankle-Strategie-Feedback hilft (Drift ~0, best ~4 s bei kp=0.7/kd=0.6, pelvis 0.90,
hold_kp 200), aber **stabiles Stehen/Gehen wird NICHT erreicht** — er faellt tuning-abhaengig nach ~2-4 s.

**Schlussfolgerung:** Das ist genau der Grund, warum Humanoid-Locomotion praktisch immer RL nutzt.
Robustes model-based Gehen braucht einen **Ganzkoerper-Balanceregler** (LIPM/Capture-Point +
Schrittanpassung bzw. Whole-Body-QP) — ein mehrtaegiges Regelungsprojekt (CPU moeglich) — ODER eine
gelernte Policy (Cloud-GPU, wenige Stunden). Wiederverwendbar bleibt die **erstklassige IK** + Gait-
Generator + Deploy-Pipeline + der austauschbare `BalanceController`-Seam.

**Verifikation:** IK-Round-Trip 1e-6 m (beide Beine, alle Schrittziele); Stand/Gang headless im Twin.
`pytest` unveraendert (training/ ausserhalb der Suite). Tag `v0.18.0`, Push nach `Tarr0k/H2plus`.
