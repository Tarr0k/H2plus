# ADR-0003: Motion-Backend hinter `MotionPlannerInterface` (ROS2-Umstiegspunkt)

- **Status:** akzeptiert
- **Datum:** 2026-06-29
- **Kontext-Quelle:** `docs/source_plan.md`

## Kontext

Der erste Ausbau nutzt Teach-&-Replay (ADR-0001), ein späterer Ausbau soll ROS2/MoveIt2 mit echter
Bahnplanung erlauben — **ohne** den Ablaufcode neu zu schreiben.

## Entscheidung

Es gibt **ein** schmales Bewegungs-Interface `motion.base.MotionPlannerInterface` mit
`move_to(arm, pose_name)` und `follow(arm, trajectory)`. Der gesamte Ablauf- und Skill-Code ruft
ausschließlich dieses Interface. Backends:

- `TeachReplayPlanner` — heute; fährt angelernte Posen ab.
- `MoveIt2Planner` — Platzhalter; ROS2/MoveIt2 in späterer Ausbaustufe.

Welches Backend läuft, entscheidet allein der Composition Root (`app.py`). **Ein Backend-Wechsel
ändert keinen Skill und keinen Orchestrator-Knoten.**

## Konsequenzen

- ➕ ROS2-Umstieg ist lokalisiert: neues Backend implementieren + in `app.py` instanziieren.
- ➕ Tests laufen gegen das Replay-Backend mit Sim-Treiber, ohne ROS2.
- ➖ Das Interface ist bewusst minimal; reichere MoveIt2-Fähigkeiten (Constraints, Planungsgruppen)
  müssen bei Bedarf additiv ergänzt werden, ohne bestehende Signaturen zu brechen.

## Verifikation der Invariante

`grep -rE "^(from|import).*(drivers|teach_replay|moveit2|pneumatic|opcua_client)" src/h2_loader/skills src/h2_loader/core`
liefert **keine** Treffer — Skills/Core importieren nur Interfaces.
