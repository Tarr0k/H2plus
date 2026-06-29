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
