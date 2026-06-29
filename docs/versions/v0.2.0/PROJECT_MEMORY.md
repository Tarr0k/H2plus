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
