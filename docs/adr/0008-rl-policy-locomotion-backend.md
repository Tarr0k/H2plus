# ADR-0008: Gelernte RL-Policy als Locomotion-Backend

- **Status:** Akzeptiert (in Umsetzung — G1-Baseline trainiert, H2-Training läuft)
- **Datum:** 2026-07-07
- **Kontext-Quelle:** Anwender-Vorgabe („ohne neue GPU weiter, Tage-Training ok"); empirisch verifiziert auf ematalos (M4000)

## Kontext

Der H2 muss sich zwischen Stationen bewegen (ADR-0004, Locomotion-Layer). Bisherige Optionen:

- **Onboard `LocoClient.Move`** (Unitree-Werksregler): funktioniert nur auf echter EDU-Hardware im Debug-Modus, ist eine Blackbox, im Twin nicht verfügbar.
- **Modellbasierter Gehregler** (v0.18.0, `training/gait/`): IK exzellent, aber ein rein positionsgeregelter H2 ist ein instabiles Gleichgewicht — steht/​läuft nur ~2–4 s, selbst mit Ankle-Balance. Ein robuster Ganzkörper-Regler (LIPM/WBC) wäre ein mehrwöchiges Regelungsprojekt.

**Befund:** Genau deshalb dominiert **Reinforcement Learning** bei Humanoid-Locomotion. Verifiziert (v0.19–0.20), dass RL-Training via **MuJoCo Playground (MJX) + Brax PPO** sogar auf der vorhandenen alten Quadro M4000 (sm_52, 8 GB) läuft — G1-Baseline konvergiert (reward 7,09, stabiles Gehen), H2-Env gebaut und im Training.

**Frage:** Soll die gelernte RL-Policy das Standard-Locomotion-Backend werden?

## Entscheidung

Ja. **Eine trainierte RL-Policy (MJX/Playground/Brax-PPO, `training/rl/`) ist das Locomotion-Backend** für das Gehen des H2.

### Einordnung in die Architektur (nichts am Ablaufcode ändert sich)

Die Policy ist ein **Velocity-Tracking-Regler**: Eingabe = Geschwindigkeitsbefehl (vx, vy, ω) + Roboterzustand (Obs), Ausgabe = Gelenk-Sollwerte @50 Hz. Damit sitzt sie auf **derselben Ebene wie `LocoClient.Move`** (`VelocitySink`, ADR-0004) — nur gelernt statt Werksregler:

```
Skills/Core → LocomotionInterface.move_to(station)
            → NavigatingLocomotion (Pfad/Lokalisierung)
            → Geschwindigkeitsbefehl (vx,vy,ω)
                 ├─ Twin/Ziel:   RL-Policy  → Gelenk-Sollwerte → RobotDriver (mujoco_sim / unitree_sdk low-level)
                 └─ HW-Fallback: LocoClientVelocitySink → LocoClient.Move (Unitree-Onboard)
```

### Umsetzung

1. **Training** (`training/rl/`): H2-Env aus der G1-Vorlage (`train_playground.py --env H2JoystickFlatTerrain`), GPU-RL, Checkpoints auf Platte.
2. **Deploy** (`training/deploy/deploy_playground_policy.py`): lädt die Policy (make_inference_fn + params), rollt sie im Twin aus, misst/rendert. An der G1-Policy validiert.
3. **Anbindung**: Die Policy erzeugt Gelenk-Sollwerte, die der bestehende `RobotDriverInterface` sendet (`mujoco_sim_driver` im Twin, `unitree_sdk_driver` low-level auf HW). Die Navigations-Geschwindigkeitsbefehle sind der Kommando-Eingang der Policy.
4. **Obs-Vertrag**: Die Beobachtung muss exakt dem Trainings-Env-Format entsprechen (H2 `joystick.py::_get_obs`). Im Twin liefert das die MJX-Env; auf HW muss sie aus Sensoren rekonstruiert werden (offener HW-Schritt).

### Unverändert

- Navigation/Lokalisierung, `LocomotionInterface`, `VelocitySink`-Muster (ADR-0004)
- SafetySupervisor + hardwired Safety (ADR-0005) — Policy-Ausgaben werden geclampt
- Onboard `LocoClient.Move` bleibt **Hardware-Fallback**
- Manipulation bleibt getrennt (Teach-in heute, GR00T Ziel — ADR-0007). **Laufen (RL, Beine) und Greifen (GR00T, Arme) sind getrennte Policies.**

## Konsequenzen

**Positiv:** robustes Gehen ohne Werksregler-Blackbox; im Twin lauffähig (kein EDU-Hardware-Zwang zum Testen); trainierbar auf vorhandener Hardware; sauber austauschbar hinter dem bestehenden Interface.

**Negativ / offen:** Training braucht GPU (M4000 reicht, aber langsam — ~Tage/Lauf); Reward/Hyperparameter noch von G1 geerbt (H2 evtl. Nachtunen); **Obs-Rekonstruktion aus echten Sensoren** ist ein offener Hardware-Schritt; Inferenz-Deployment aktuell an das MJX-Env gekoppelt (für HW später Obs-Bridge + onboard-Inferenz nötig).

**Verifikation:** G1-Policy im Deploy-Harness reward 9–12, 300–400 Schritte ohne Sturz; H2-Training läuft (v0.20/0.21). Siehe `PROJECT_MEMORY.md` 2026-07-06/07.
