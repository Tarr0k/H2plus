# ADR-0006: Schritt-Ebene auf UDT — kohärenter PLC-Store

- **Status:** akzeptiert
- **Datum:** 2026-06-29
- **Kontext-Quelle:** PROJECT_MEMORY v0.2.0-Folgeschritt

## Kontext

Bis v0.5.1 liefen zwei parallele „PLC-Stores", die Schritt-Ebene der Skills über ein flaches `Signal`-Enum
(`PlcInterface`/`OpcUaPlcClient`), während die Job-Ebene bereits über die OPC-UA-UDT (`H2HandshakeClient`)
lief. Das war als bewusste Schuld in v0.2.0 dokumentiert: zwei Wahrheitsquellen, inkohärent, lossy Mapping.

Besonders problematisch:
- Die Schritt-Ebene der Skills konnte Maschinenzustände (Türzustand, Spannvorrichtung-Zustand) nicht
  semantisch abfragen — nur flache Signal-Boolean lesen.
- Der Handshake zwischen Roboter und PLC (Clamp-Anforderung, Clamp-Rückmeldung, Tür-Zustand) war über
  zwei unterschiedliche Pfade verdrahtet.
- Das redundante `ROBOT_DONE`-Schreiben der Skills beim Job-Abschluss kollidierte konzeptionell mit dem
  `JobRunner`, der denselben Signal via `finish_job` setzen wollte.

## Entscheidung

**Schritt-Ebene auf UDT-Fassade `plc.machine_io.MachineIo` führen.**

Die Schritt-Ebene der Skills wird über eine neue, semantische Fassade `MachineIo` ebenfalls auf die UDT
geführt. `MachineIo` bietet folgende Methoden:

- **Abfragen:** `door_open()`, `fixture_free()`, `cycle_done()`
- **Anforderungen:** `request_open_clamp()`, `request_close_clamp()`
- **Warten:** `wait_clamp_open()`, `wait_clamp_closed()`
- **Schreiben:** `set_gripper_holds(bool)`, `set_current_step(str)`

Intern liest/schreibt `MachineIo` die UDT-Member in `plcToRobot`/`robotToPlc` über den existierenden
`H2HandshakeClient`.

**Simulator und Stub-Verhalten:**

Der `PlcSimulator` bedient die UDT-Maschinenzustände (`door`, `clamp_open`, `cycle_done`) direkt und
reagiert via `service_requests()` auf Roboter-Anforderungen (Clamp-Öffnen/Schließen, Tür-Verriegelung).
Der `MachineIo`-Responder ruft diese Service-Methoden **synchron** im Stub auf.

Auf dem **Zielsystem** (echter PLC via OPC-UA) wird stattdessen per Polling/Subscription die UDT
gelesen und durch die echte PLC-Logik aktualisiert.

**SkillContext und Legacy:**

- `SkillContext.plc` wird umbenannt in `SkillContext.machine`, gibt `MachineIo`-Instanz zurück.
- Das flache `Signal`-Enum, `PlcInterface` und `OpcUaPlcClient` bleiben als **Legacy** bestehen (nicht
  gelöscht), werden aber von den Skills nicht mehr genutzt — das erlaubt Rückwärts-Kompatibilität für
  Code außerhalb dieser Repo.
- Das redundante `ROBOT_DONE`-Schreiben durch Skills entfällt. **Job-Abschluss ist Sache des `JobRunner`**,
  nicht des Skill.

## Konsequenzen

### ➕ Positive Konsequenzen

- ✓ **Ein einziger Wahrheits-Store:** Beide Ebenen (Job, Schritt) lesen/schreiben die gleiche UDT über
  `H2HandshakeClient`. Konsistenz, keine lossy Mappings mehr.
- ✓ **Semantisch reiches Interface:** Statt `signal_read(Signal.CLAMP_OPEN)` schreiben Skills jetzt
  `machine.wait_clamp_open()` — **Intent ist klar, Testbarkeit ist besser**.
- ✓ **Handshake ist kohärent:** Tür/Clamp-Sequenzen folgen einem einzigen Pattern (UDT-Member über
  `H2HandshakeClient`), unabhängig ob Job- oder Schritt-Ebene.
- ✓ **Näher an echter OPC-UA-Anbindung:** Das `MachineIo`-Interface kann später auf OPC-UA-Polling/Subscription
  umgestellt werden, ohne Skill-Code zu ändern.
- ✓ **SimPlanner + Stub sind testbar:** Der synchrone `PlcSimulator.service_requests()`-Responder erlaubt
  Unit-Tests für Maschinen-Handshakes ohne echten PLC.

### ➖ Negative Konsequenzen & Limitations

- ⚠️ **`MachineIo.wait_*` ist im Stub nicht-blockierend:** Der Responder arbeitet synchron, ruft Service
  auf, gibt sofort zurück. Im echten System (OPC-UA-Polling) wird `wait_clamp_open()` länger warten müssen
  — diese Semantik muss mit `timeout`-Parametern oder expliziter Fehlerbehandlung abgesichert sein.
- ⚠️ **Legacy-Signal-Schicht bleibt Code-Leichen:** `Signal`, `PlcInterface` und `OpcUaPlcClient` sind
  nicht gelöscht, auch wenn nicht mehr verwendet. Technische Schuld für potenziellen zukünftigen Cleanup.
- ⚠️ **Migrations-Aufwand:** Alle existierenden Skills müssen von `SkillContext.plc` + flachen Signals
  auf `SkillContext.machine` + semantische Methoden umgestellt werden.

## Verifikation

1. **UDT-Schnittstelle:** `docs/plc_interface.md` dokumentiert die UDT-Member (`plcToRobot.*`, `robotToPlc.*`,
   `machineState.*`) und ihre Semantik.
2. **SDK-Referenz:** `docs/sdk_reference.md` dokumentiert `MachineIo`-Methoden und deren Verhalten im Stub.
3. **PlcSimulator:** `test_plc_interface.py` prüft `service_requests()` und Zustandsübergänge; alle Tests
   grün.
4. **Skill-Migration:** Alle Skills in `src/h2_loader/skills/` importieren nur `MachineIo`, nicht `PlcInterface`.
5. **SkillContext:** `SkillContext.machine` ist vorhanden; `SkillContext.plc` ist deprecated.

---

**Abhängige ADRs:**
- ADR-0001 (Python SDK, Unitree-Bewegung)
- ADR-0002 (Pneumatikgreifer)
- ADR-0003 (Motion-Backend Interface)
- ADR-0005 (Sicherheitskonzept — OPC-UA-Signale)

**Gültig ab:** 2026-06-29
