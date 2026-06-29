# ADR-0005: Sicherheitskonzept — getrennt/abgesichert + funktionaler Supervisor

- **Status:** akzeptiert
- **Datum:** 2026-06-29
- **Kontext-Quelle:** Betriebssicherheits-Anforderung des Maschinenlader-Systems

## Kontext

Der Unitree H2 PLUS bewegt sich in einer Induktionshärte-Anlage, um Werkstücke zu laden/entladen und
Induktoren zu wechseln. Er ist ein **laufender, 70-kg-Humanoider Roboter** (1,8 m Höhe), keine starre
Plattform. Damit entstehen neue Sicherheitsanforderungen:

1. **Mobilitäts-Gefahren:** Ein laufender Roboter kann stürzen, gegen Hindernisse fahren, personen verletzen.
2. **Sicherheits-Partitionierung:** Die Software allein kann diese nicht lösen. Es gibt eine separate,
   zertifizierte Sicherheits-SPS mit hardwired Schutzlogik (Not-Halt, Schutzfeld, Bremsgruppen, F-Signale).
3. **Funktionales Monitoring:** Die OPC-UA-Schnittstelle (v0.1.1) bietet Spiegel-Signale (`robotEnable`,
   `safeZoneClear`, `estopFromPlc`, Heartbeat); die Anwendung muss diese abfragen und Ablauf-Entscheidungen treffen.

## Entscheidung

**1. Betriebsart: Getrennt/Abgesichert (Separated Operation)**

Der Roboter arbeitet in einem **physisch abgesicherten Bereich** (Schutzraum mit Zaun, Lichtgitter,
Trittmatten). Außerhalb ist eine Person anwesend. Eindringt die Person in den Schutzraum während der
Roboter läuft/manipuliert, werden alle Bewegungen sofort durch **hardwired Sensorik und
Sicherheits-SPS** gestoppt — nicht durch die Software.

**2. Hardwired Safety vs. Software-Supervisor**

- **Hardwired (Safety-SPS):** E-Stop, Schutzfeld-Sensor-Auslöser, Not-Halt-Kreis, Druckluft-Sperrmagnete,
  Bremsgruppen, Funktion-Stopp (Safety-gated). **Diese sind zertifiziert und verlässlich.**
  
- **Software-`SafetySupervisor` (funktional):** Liest OPC-UA-Spiegel-Signale aus der Sicherheits-SPS
  (`robotEnable`, `safeZoneClear`, `estopFromPlc`), wertet Heartbeat-Watchdog aus, blockiert neue Bewegungsbefehle
  wenn unsicher. Ist **nicht sicherheitsgerichtet** und ersetzt keinen Schutz.

Die Software sperrt den `JobRunner` (Ablaufebene) und `Locomotion` (Bewegungsebene), wenn ein Sperr-Signal
aktiv ist. Das ist ein Sicherheits-**Gating** auf Ablauf-Ebene, aber das echte Halten der Maschine liegt
bei der Hardware.

**3. Zonenmodell (funktional)**

Der Arbeitsbereich ist in 5 funktionale Zonen eingeteilt, jede mit Geschwindigkeits-Limit:
- `transit` ≤ 0,8 m/s — Korridor
- `machine_zone` ≤ 0,3 m/s — Maschine selbst
- `storage_zone` ≤ 0,5 m/s — Rohteile-Lager
- `dropoff_zone` ≤ 0,5 m/s — Fertigteil-Kiste
- `shelf_zone` ≤ 0,3 m/s — Induktor-Regal

Station (`home`, `part_storage`, `machine`, `dropoff_box`, `inductor_shelf`) mappt zu Zone.
Geschwindigkeits-Limits sind **Platzhalter** und werden bei Risikobeurteilung konkretisiert.

**4. Humanoid-spezifische Gefahr: Sturz**

Ein laufender 1,8-m-/70-kg-Roboter kann **stürzen**. Das ist nicht durch diese Software verhinderbar.
- **Unitree-Onboard-Regler (PC1):** Balanceiert den Roboter während des Gangs; **proprietär, sperrbar, nicht durch diese Software änderbar.**
- **Hardware:** Beinfeder-Stärke, Schwerpunkt.
- **Umgebung:** Ebener, unbehinderter Boden.

Software-Beitrag: Geschwindigkeits-Limits, Bereichsfreigabe, ggf. später Sturz-Detektor.
Aber: Ein Sturz ist akzeptieren als Residualrisiko oder durch Fallmatten / Umgebungsgestaltung zu mindern.

## Konsequenzen

### ➕ Positive Konsequenzen

- ✓ **Klare Verantwortung:** Hardwired Safety ist zertifizierbar und liegt beim Integrator; Software ist
  funktionales Gating und Ablauf-Spiegel.
- ✓ **Getrennt/Abgesichert ist Standard:** Bewährte Betriebsart für Industrieroboter und fahrerlose Fahrzeuge;
  keine anspruchsvolle Ko-Präsenz-Sensorik / Kraft-Limitierung.
- ✓ **OPC-UA-Watchdog realisierbar:** Heartbeat-Toggle ist einfach, robustig gegen Netzwerk-Jitter.
- ✓ **Zonenmodell ist erweiterbar:** Neue Stationen + Geschwindigkeits-Limits später hinzufügbar ohne Architektur-Änderung.
- ✓ **Onboard-Locomotion ist sicher:** Unitree PC1-Regler ist gesperrte Firmware; nicht durch diese Code-Ausbau änderbar.

### ➖ Negative Konsequenzen & Limitations

- ⚠️ **Diese Software ist NICHT sicherheitsgerichtet.** Der Supervisor ist funktional. Eine echte
  Sicherheits-SPS mit F-Signalen ist zwingend.
- ⚠️ **Risikobeurteilung ist pflicht:** Eine vollständige Analyse nach ISO 12100 ist Verantwortung des
  Integrators. Diese Dokumentation ersetzt sie nicht.
- ⚠️ **Sturz ist nicht gelöst:** Ein laufender Humanoider kann fallen. Keine Software-Lösung dafür.
  Residual-Risiko oder Fallmatten nötig.
- ⚠️ **OPC-UA ist nicht Echtzeit:** Heartbeat-Polling ist nicht deterministisch. Nur bedingt für echte
  Not-Halt-Funktionen geeignet (darum: hardwired E-Stop, nicht OPC-UA).
- ⚠️ **Hindernis-Ausweichung ist nicht implementiert:** Der Roboter hat kein Dunstensor-Netzwerk für
  Echtzeit-Navigation. Fahrtwege müssen vorgeplant / eingemessen sein.

## Verifikation

1. **Hardwired Safety Schaltplan:** Sicherheits-SPS-Programm (TIA, mit Funktionalem Schaltbild) zeigt
   E-Stop, Schutzfeld-Auslöser → Bremsgruppen.
2. **OPC-UA-UDT Heartbeat:** `test_plc_interface.py` prüft Toggle-Logik und Timeout-Erkennung (✓ grün).
3. **SafetySupervisor Gating:** `JobRunner.step()` fragt `supervisor.is_safe()` ab bevor Job akzeptiert wird.
4. **Locomotion Geschwindigkeit:** `OnboardLocomotion.move_to()` liest Limit aus `config/stations.yaml`.
5. **Inbetriebnahme-Validierung:** Wird Sache des Integrators (E-Stop-Test, Schutzfeld-Test, Heartbeat-Ausfall-Szenario).

---

**Abhängige ADRs:**
- ADR-0001 (Python SDK) — Unitree-API
- ADR-0002 (Pneumatikgreifer + Ventil-Port) — Endeffektor-Sperrmöglichkeit
- ADR-0003 (Motion-Backend Interface) — Bewegungsplaner wechselbar
- ADR-0004 (Locomotion Interface) — Lauf-Backend isoliert

**Referenz:** `docs/safety_concept.md` (ausführliches Konzept mit Normen, Risikobeurteilung, nächsten Schritten)

**Gültig ab:** 2026-06-29
