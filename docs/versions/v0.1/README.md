# h2_loader — Maschinenlader für den Unitree H2 PLUS

Strukturiertes Python-Gerüst, mit dem ein **Unitree H2 PLUS** (zweiarmiger Humanoid, 7 DoF je Arm)
an einer feststehenden **Induktionshärtemaschine Werkstücke lädt und entlädt**. Spätere Ausbaustufe:
**Induktorwechsel** (in einer Führung mit 2 Schrauben). Endeffektor je Arm ist ein **einfacher
pneumatischer Backengreifer** (1 Zylinder, auf/zu).

> **Stand v0.1 — Gerüst + Stubs.** Lauffähiges Paket mit Interfaces, Konfiguration und durchlaufender
> Lade-Sequenz in der Simulation. **Keine echte Roboterbewegung.** Reale Ausführung erst auf dem
> Ubuntu-Zielsystem.

## Warum so gebaut

Die Architektur ist auf **Austauschbarkeit** ausgelegt:

- **Motion-Backend tauschbar:** Ablaufcode ruft nur `MotionPlannerInterface`. Heute `TeachReplayPlanner`
  (angelernte Posen abfahren), später `MoveIt2Planner` (ROS2/MoveIt2) — **kein Skill ändert sich**.
- **Endeffektor tauschbar:** Skills rufen nur `EndEffectorInterface.grasp()/release()`. Heute
  `PneumaticGripper`, später `DexHand` oder ein Schrauber für den Induktorwechsel.
- **Ventil-Anbindung offen:** Der Greifer bekommt einen `ValveActuator` injiziert — SPS (`PlcValveActuator`)
  **oder** bordeigene H2-IO (`H2IoValveActuator`). Entscheidung vertagt, Architektur offen.
- **Sim-to-Real:** `RobotDriverInterface` mit `MujocoSimDriver` (Test) und `UnitreeSdkDriver` (real),
  Auswahl per `config/robot.yaml` (`driver: sim|sdk`).

Details: [`docs/architecture.md`](docs/architecture.md) und die ADRs unter [`docs/adr/`](docs/adr/).

## Setup

```bash
# Im Verzeichnis h2_loader/
pip install -e .[sim,plc]        # Kern + Simulation + SPS-Anbindung
# weitere Extras: [ros2] (späterer ROS2-Umstieg), [ai] (KI-Greifen), [dev] (pytest)
```

Python ≥ 3.10. Reale Hardware-/Sim-Ausführung läuft auf Ubuntu 22.04 (CycloneDDS, `unitree_sdk2_python`).

## Ausführen (Dry-Run, Simulation)

```bash
python -m h2_loader.app --driver sim
```

Tickt den Behavior-Tree der Lade-Sequenz durch; die Stubs loggen jeden Schritt
(*warte Tür offen → zur Aufnahme fahren → greifen → einlegen → ROBOT_DONE an SPS*) und terminieren sauber.

CLI-Optionen: `--config` (robot.yaml), `--plc-config` (plc.yaml), `--driver sim|sdk`, `--poses-dir`.

## Tests

```bash
pytest          # HAL / Motion / Skills gegen Mock-SPS + Sim-Treiber, ohne Hardware
```

## Projektstruktur (Kurzform)

```
src/h2_loader/
  app.py            Composition Root: Config -> Komponenten -> Orchestrator
  core/             Ablaufsteuerung (py_trees-Orchestrator, Skill-Knoten, Safety)
  skills/           Anwendungs-Skills (load/unload, change_inductor=Zukunft)
  motion/           Bewegungs-Backend hinter Interface (teach_replay | moveit2)
  hal/              Roboter, Arm, Endeffektoren, Lowlevel-Treiber
  perception/       Wahrnehmung (Stub, für späteren Ausbau)
  plc/              Maschinen-SPS (OPC-UA) + Signal-Enum
  util/             Config-Loader, Logging
config/             robot.yaml, machine.yaml, plc.yaml, poses/*.yaml
docs/               architecture.md, adr/, source_plan.md, versions/
tests/              pytest gegen Mock/Sim
```

## Projekt-Memory & Versionierung

Entscheidungen werden **append-only** festgehalten — nichts wird gelöscht:

- [`PROJECT_MEMORY.md`](PROJECT_MEMORY.md) — chronologisches Entscheidungs-/Statuslog.
- [`docs/adr/`](docs/adr/) — Architecture Decision Records (immutable, je Entscheidung eine Datei).
- [`docs/versions/`](docs/versions/) — Snapshot-Ordner je Meilenstein (`v0.1` = Initialstand).
