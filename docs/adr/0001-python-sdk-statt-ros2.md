# ADR-0001: Python-SDK (Teach-&-Replay) statt ROS2 im ersten Ausbau

- **Status:** akzeptiert
- **Datum:** 2026-06-29
- **Kontext-Quelle:** `docs/source_plan.md`

## Kontext

Der Maschinenlader soll feste Posen anfahren (Werkstück greifen → einlegen → entnehmen). Das Team
hat keine ROS2-Erfahrung; ein voller ROS2/MoveIt2-Stack wäre für den ersten Ausbau überdimensioniert
und schwer zu betreiben. Bewegung soll per **Teach-in fester Posen** über das **`unitree_sdk2_python`**
erfolgen — nah an klassischer Einarm-Roboter-Programmierung.

## Entscheidung

Im ersten Ausbau wird die Bewegung über ein **Teach-&-Replay-Backend** (`TeachReplayPlanner`)
realisiert, das angelernte Posen aus `config/poses/*.yaml` über die HAL abfährt. ROS2/MoveIt2 wird
**nicht** eingesetzt.

Damit ein späterer Umstieg möglich bleibt, läuft **aller Ablaufcode ausschließlich gegen
`MotionPlannerInterface`** (siehe ADR-0003). Ein ROS2-Backend (`MoveIt2Planner`) ist als Platzhalter
angelegt und wird im Extra `[ros2]` ausgelagert, damit der ROS2-Stack kein harter Import ist.

## Konsequenzen

- ➕ Schlanker, sofort betreibbarer Stack; gleiche DDS-Schnittstelle wie MuJoCo-Sim → Sim-to-Real.
- ➕ Kein ROS2-Know-how nötig, um die Lade-Sequenz zu betreiben.
- ➖ Keine echte Bahnplanung/Kollisionsvermeidung im ersten Ausbau (nur Punkt-zu-Punkt geteachte Posen).
- ↪ Umstieg auf MoveIt2 = neues Backend hinter dem Interface registrieren, ohne Skill-Änderung.
