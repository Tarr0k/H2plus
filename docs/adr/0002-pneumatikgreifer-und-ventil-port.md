# ADR-0002: Pneumatischer Backengreifer + Ventil-Anbindung als Port

- **Status:** akzeptiert
- **Datum:** 2026-06-29
- **Kontext-Quelle:** `docs/source_plan.md`

## Kontext

Als Endeffektor je Arm ist ein **einfacher pneumatischer Backengreifer (1 Zylinder, auf/zu)**
vorgesehen — *nicht* die optionalen Unitree-Mehrfingerhände. Wie das Greiferventil physisch
geschaltet wird, ist **noch offen**: entweder über die Maschinen-SPS (digitaler Ausgang / OPC-UA)
oder über die bordeigene H2-IO (RS485/CAN).

## Entscheidung

1. **Endeffektor-Abstraktion:** Skills rufen nur `EndEffectorInterface` (`grasp/release/is_holding`).
   Konkret heute `PneumaticGripper`. Mehrfingerhand (`DexHand`) und Schrauber für den Induktorwechsel
   sind als austauschbare Endeffektoren vorgesehen.
2. **Ventil als Port (Dependency Injection):** `PneumaticGripper` bekommt einen `ValveActuator`
   injiziert. Es gibt zwei austauschbare Implementierungen:
   - `PlcValveActuator` — schaltet über die Maschinen-SPS.
   - `H2IoValveActuator` — schaltet über die bordeigene H2-IO.
   Die konkrete Wahl ist **vertagt**; Default im Composition Root (`app.py`) ist aktuell
   `H2IoValveActuator`. Ein Wechsel betrifft nur `app.py`.

## Konsequenzen

- ➕ Greifer-Hardware und Ventil-Anbindung sind unabhängig voneinander austauschbar.
- ➕ Entscheidung SPS vs. H2-IO kann ohne Code-Umbau später getroffen werden.
- ➖ Ohne Greifkraft-/Positionssensorik liefert `is_holding()` nur den angenommenen Zustand.
- ↪ Der Induktorwechsel braucht einen anderen Endeffektor (Schrauber) + Werkzeugwechsel — genau
  deshalb ist diese Abstraktion zentral (siehe `skills/change_inductor.py`).
