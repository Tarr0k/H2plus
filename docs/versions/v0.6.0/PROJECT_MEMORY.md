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
