# ADR-0004: H2 ist mobil — Locomotion hinter `LocomotionInterface`

- **Status:** akzeptiert
- **Datum:** 2026-06-29
- **Kontext-Quelle:** Anwender-Vorgabe (Korrektur zu `docs/source_plan.md`)

## Kontext

Der ursprüngliche Plan (`source_plan.md`, Phase 1) ging von einem auf einer **fest montierten Plattform
stehenden** Roboter aus. Diese Annahme ist **falsch**: Der H2 PLUS muss sich in der Zelle **bewegen** —
er holt Rohteile aus dem Teilelager, bringt sie zur Maschine, legt Fertigteile z. B. in eine Kiste und
holt beim Werkzeugwechsel einen Induktor aus einem Regal. Fortbewegung ist damit fester Bestandteil des
Ablaufs, nicht nur Manipulation an einem festen Ort.

## Entscheidung

Es gibt **ein** schmales Lauf-Interface `hal.locomotion.base.LocomotionInterface` mit
`move_to(station)`, `current_station()` und `stop()`. Der gesamte Ablauf-/Skill-Code lässt den Roboter
ausschließlich über dieses Interface zwischen **benannten Stationen** (`config/stations.yaml`:
`home`, `part_storage`, `machine`, `dropoff_box`, `inductor_shelf`) laufen. Backends:

- `OnboardLocomotion` — **heute (Standard)**; kommandiert den **bordeigenen Lauf-/Balance-Regler des
  H2 PLUS (PC1) über das SDK** (High-Level-Geh-/Wegpunktbefehl). Im Stub-Stand nur Logging.
- *Später austauschbar*: RL-trainierte Policy (z. B. via `unitree_rl_gym`) oder ROS2-Navigation —
  ohne Skill-Änderung.

Welches Backend läuft, entscheidet allein der Composition Root (`app.py`). Skills komponieren Laufen +
Manipulation (z. B. *Laden* = laufe zu `part_storage` → greifen → laufe zu `machine` → einlegen).

## Begründung der Backend-Wahl (Onboard statt RL-Training)

`unitree_rl_gym` ist ein **Trainings**-Baukasten für Lauf-Policies und **unterstützt den H2 nicht**
(nur Go2/G1/H1/H1_2 → Asset-Portierung + Isaac Gym + RTX nötig). Der H2 PLUS bringt auf PC1 einen
gesperrten Onboard-Lauf-/Balance-Regler mit; dieser wird über das SDK kommandiert. Eigenes RL-Training
ist nur Fallback, falls kein brauchbarer Onboard-Geh-Modus verfügbar ist.

## Konsequenzen

- ➕ Lauf-Backend ist lokalisiert: neues Backend implementieren + in `app.py` instanziieren.
- ➕ Skills sind mehrstufig (laufen + manipulieren), Stationen rein konfigurativ einmessbar.
- ➖ **Sicherheit wächst erheblich:** ein laufender Roboter in der Zelle ist eine andere Risikoklasse
  (Bereichsüberwachung, dynamische Hindernisse, Personenschutz). Das ist hier noch **nicht** gelöst und
  als eigener Sicherheits-Folgeschritt vorgemerkt.
- ➖ Das Interface ist bewusst minimal (Station-zu-Station); Pfadplanung/Hindernisvermeidung müssen bei
  Bedarf additiv ergänzt werden.

## Verifikation der Invariante

`grep -rE "^(from|import).*(onboard_locomotion|drivers|teach_replay|moveit2|pneumatic|opcua_client)" src/h2_loader/skills src/h2_loader/core`
liefert **keine** Treffer — Skills/Core importieren nur Interfaces, nie konkrete Backends.

## Nachtrag (2026-06-29, SDK-Grounding)

Prüfung der echten SDK-Beispiele (`unitree_sdk2_python`, `example/h2/high_level/h2_loco_client_example.py`)
ergab: der Onboard-`LocoClient` ist **velocity-/FSM-basiert** (`Move(vx,vy,ω)`, `SetVelocity`, `Start`,
`StandUp`, `StopMove`) und bietet **kein** Wegpunkt-/Positionsfahren. Das Interface `move_to(station)`
bleibt gültig, aber sein **Onboard-Backend benötigt zusätzlich eine Lokalisierungs- + Pfad-/Regelschicht**
(z. B. `unilidar_sdk2` + `point_lio_unilidar`, oder `unitree_ros2` + Nav2). Bis diese existiert, ist
`OnboardLocomotion` ein Platzhalter ohne autonome Navigation. Details: `docs/sdk_reference.md`.
