# Ursprungsplan (Kontextquelle)

> Dieser Plan ist die Quelle für die Entscheidungen in `PROJECT_MEMORY.md` und den ADRs. Er ersetzt
> das im ursprünglichen Entwurf referenzierte `unitree_h2_dokumentation.md`, das in der
> Umsetzungsumgebung nicht vorhanden war. Festgehalten zum Stand v0.1 (2026-06-29).

## Ziel

Ein **Unitree H2 PLUS** (zweiarmiger Humanoid, 7 DoF je Arm) lädt/entlädt Werkstücke an einer
feststehenden Induktionshärtemaschine. Ausbaustufe 2: Induktorwechsel (Führung, 2 Schrauben).
Endeffektor je Arm: einfacher pneumatischer Backengreifer (1 Zylinder, auf/zu) — nicht die
Unitree-Mehrfingerhände.

Es soll ein **strukturell sauberes Python-Gerüst** entstehen, sodass (a) Endeffektoren tauschbar
sind, (b) ein späterer Umstieg auf ROS2/MoveIt2 ohne Umschreiben des Ablaufcodes möglich ist, (c) ein
**append-only Projekt-Memory** alle Entscheidungen festhält. Tiefe bewusst: Struktur + Interfaces +
Stubs — keine echte Roboterbewegung.

## Getroffene Entscheidungen

- **Bewegung:** Teach-in fester Posen über das Python-SDK (`unitree_sdk2_python`), kein ROS2 jetzt;
  Architektur so, dass ROS2/MoveIt2 als Backend nachrüstbar ist. → ADR-0001, ADR-0003.
- **Greifer-Ventil:** abstrahiert (Treiber-/Port-Pattern); konkrete Anbindung (SPS vs. H2-IO) später.
  → ADR-0002.
- **Code-Tiefe:** Struktur + Stubs/Interfaces (lauffähiges Gerüst, abstrakte Basisklassen, Konfigs,
  Docstrings; Methoden noch als Stubs).
- **Branding:** Private-Modus bestätigt → kein EMA-Logo, kein Eigentums-Footer.

## Zielumgebung

- **Laufzeit (H2 PLUS onboard):** Ubuntu 22.04, `unitree_sdk2_python` + CycloneDDS 0.10.2, `py_trees`
  für die Ablaufsteuerung, `python-opcua`/`pymodbus` zur Maschinen-SPS, OpenCV (später Open3D/Pose).
- **Entwicklung/Test (Workstation):** Ubuntu 22.04, `unitree_mujoco` (gleiche DDS-Schnittstelle →
  Sim-to-Real per Konfig-Umschaltung).

## Architektur-Prinzipien

1. Schichtentrennung `app → core → skills → {motion, hal, perception, plc}`; höhere Schichten kennen
   nur Interfaces.
2. Motion-Backend austauschbar (ROS2-Umstiegspunkt) hinter `MotionPlannerInterface`.
3. Endeffektor austauschbar hinter `EndEffectorInterface`.
4. Greifer-Ventil als injizierter Port (`ValveActuator`): `PlcValveActuator` | `H2IoValveActuator`.
5. Sim-to-Real über `RobotDriverInterface` (`MujocoSimDriver` | `UnitreeSdkDriver`), Auswahl per Config.
6. Skills sind Behavior-Tree-Knoten (`precondition/execute/recover`) für sauberen SPS-Handshake.
7. Konfiguration statt Code: Posen, Maschinengeometrie, SPS-Signale in `config/*.yaml`.

## Induktorwechsel (Ausbaustufe 2)

Ein 1-Zylinder-Greifer kann keine Schrauben lösen. Der Induktorwechsel (2 Schrauben) erfordert ein
anderes Werkzeug (Akku-/Pneumatik-Schrauber als Endeffektor) und damit einen Werkzeugwechsel
(Tool-Changer, vgl. „ATI QC"). Daher ist die Endeffektor-Abstraktion zentral: `change_inductor.py`
existiert als dokumentierter Stub, der einen `ScrewdriverEndEffector` + Tool-Change voraussetzt.

## Projekt-Memory & Versionierung

- `PROJECT_MEMORY.md` — append-only Entscheidungs-/Statuslog.
- `docs/adr/` — Architecture Decision Records (immutable).
- `docs/versions/vX.Y/` — Snapshot-Ordner je Meilenstein (`v0.1` = Initialstand).
- Git-Tags (`v0.1.0` …) zusätzlich — gesetzt im Ziel-Repository `Tarr0k/H2plus`.

## Umgebungs-Abgleich bei der Umsetzung

Die Umsetzung erfolgte in einer Remote-Session, die im EMA-Engineering-Tools-Repo lief — nicht im
H2-Greenfield-Repo. Daher wurde `h2_loader/` als selbst-enthaltenes Unterverzeichnis angelegt und per
PR gegen dieses Repo ausgeliefert. Verschieben nach `Tarr0k/H2plus` + Tagging erfolgen lokal durch
den Anwender. Das ursprünglich referenzierte `unitree_h2_dokumentation.md` war nicht vorhanden und
wurde nicht erfunden; dieser Plan dient als Kontextquelle.
