# Sicherheitskonzept — h2_loader

## 1. Zweck & Geltungsbereich

Dieses Dokument definiert das Sicherheitskonzept für den Einsatz des Unitree H2 PLUS als Maschinenlader
an einer feststehenden Induktionshärtemaschine. Gegenstand ist die **Betriebsart getrennt/abgesichert**
(separated operation): Der Roboter bewegt sich in einem durch Schutzeinrichtungen (Zaun, Schutzfeld,
Lichgitter, Trittmatten) abgesicherten Bereich. **Eine Person, die in diesen Bereich eindringt während
der Roboter läuft oder sich manipuliert, sperrt alle Bewegungen sofort (sicherer Halt).**

> ### ⚠️ Kritisch: Diese Software ist NICHT sicherheitsgerichtet.
>
> Der Software-`SafetySupervisor` (nachfolgend beschrieben) ist eine **funktionale Überwachungsschicht**
> und ersetzt keinen zertifizierten Schutz. Die **eigentliche Sicherheit** (Not-Halt, Schutzfeld-Stopp,
> Personenerkennung, sichere Zonen-Freigabe) ist **hardwired und zertifiziert** in einer separaten
> Sicherheits-SPS (Safety-Controller) mit F-Signalen und zweikanaliger Auslegung. Der Software-Supervisor
> fordert diese Zustände an, hält den Ablauf an, spiegelt Signale — mehr nicht. **Diese Dokumentation
> ersetzt keine Risikobeurteilung, keine Auswahl/Anordnung von Schutzeinrichtungen und keine
> Inbetriebnahmevalidierung durch qualifizierte Sicherheitstechniker.**

## 2. Verantwortungs-Split: Hardwired Safety vs. funktionaler Supervisor

Die folgende Tabelle zeigt, welche Maßnahme wo realisiert ist und wer dafür verantwortlich ist:

| Maßnahme | Realisierung | Verantwortung |
|----------|--------------|---------------|
| **Not-Halt (E-Stop)** | Hardwired, zweikanalig, Sicherheits-SPS mit F-Signalen | Zertifizierter Sicherheitstechniker; Hardware-Integrator |
| **Schutzfeld-/Lichtgitter-Stopp** | Hardwired, direkt zur Sicherheits-SPS (keine Software-Vermittlung) | Sensorik + Integrator; F-Signale der Safety-SPS |
| **Trittmatte, Trittschalter** | Hardwired zur Sicherheits-SPS | Integrator |
| **Bereichsfreigabe (Zone ist sicher?)** | Hardwired Sensor-Eingänge → Safety-SPS | Sensorik + Integrator |
| **Auftrags-Freigabe (Maschine erlaubt Roboter?)** | Toggle-basierter Handshake in OPC-UA (`robotInMachine`) | PLC-Programmierer (TIA Portal), H2-Anwendungscode |
| **Ablauf-Freigabe (darf Skill jetzt bewegen?)** | Funktionaler `SafetySupervisor` vor `JobRunner` | `SafetySupervisor` (h2_loader); abgesichert durch hardwired Enable-Signal der SPS |
| **Zonen-Logik (Geschwindigkeit pro Station)** | Funktional im `OnboardLocomotion` Backend | h2_loader/Ablaufcode |
| **Watchdog-Heartbeat (SPS ↔ H2 lebt noch?)** | Toggle-basiert in `H2HandshakeClient` + `PlcSimulator` | Beidseitig: PLC-Code + h2_loader |
| **Sturz/Stabilitätsverlust (70 kg, 1,8 m Roboter läuft/fällt)** | Hardwired im Onboard-Balance-Regler (Unitree PC1) + Hardware-Eigenschaften | Unitree (gesperrter Onboard-Regler, nicht durch diese Software änderbar) |

## 3. Betriebsart: Getrennt/Abgesichert (Separated Operation)

**Definition:** Der Roboter bewegt sich in einem **physisch abgesicherten Bereich** (Schutzraum).
Außerhalb ist eine arbeitende Person mit unbegrenztem Zugang vorhanden (typischerweise der Maschinenbediener).

**Logik der Zugangskontrolle:**
1. **Zutritts-Sensor** (z.B. Lichtgitter, Schutzfeld) überwacht die Grenze des abgesicherten Bereichs.
2. Wenn Person eindringt → Sensor auslöst → Sicherheits-SPS fährt alle Roboter-Achsen + Fortbewegung sofort in den sicheren Zustand (Bremsgruppen, Sperrmagnete).
3. **Keine Ko-Präsenz während Bewegung.** Der Roboter kann sich wieder bewegen, sobald der Bereich frei ist (gemäß Sensor).
4. **Reset:** Typischerweise durch **bestätigen + Quittieren** des Not-Halts (ggf. mit Schlüsselschalter) durch einen Verantwortlichen außerhalb des Schutzraums.

**Software-seitige Vorbedingung (`SafetySupervisor`):** Der Ablaufcode fragt den funktionalen Supervisor ab:
„Ist die Zone momentan klar? Erlaubt die SPS das Bewegen?" Dieser Supervisor liest Spiegel-Signale aus der OPC-UA-UDT
(`safeZoneClear`, `robotEnable`) und wertet den Heartbeat aus. Ist der Supervisor selbst nicht sicher (z.B. Heartbeat weg),
blockiert er. **Aber dieser Check ersetzt nicht die hardwired Sensorik.**

## 4. Zonenmodell

Der Arbeitsbereich ist funktional in Zonen eingeteilt. Jede Zone hat eine maximale Roboter-Geschwindigkeit
(für die Manipulationsgenauigkeit und ggf. Notfalls-Bremsweg-Berechnung relevant).

| Zone | Max. Geschwindigkeit | Roboter aktiv? | Beschreibung |
|------|----------------------|----------------|-------------|
| `transit` | ≤ 0,8 m/s | Ja (Laufen) | Korridor/Park-Zone; Roboter transitiert von einer Stationengruppe zur anderen |
| `machine_zone` | ≤ 0,3 m/s | Ja (Laufen + Manipulation) | unmittelbare Nähe zur Maschine; Laden/Entladen der Werkstücke |
| `storage_zone` | ≤ 0,5 m/s | Ja (Laufen + Manipulation) | Rohteile-Lager; Roboter greift Werkstücke auf |
| `dropoff_zone` | ≤ 0,5 m/s | Ja (Laufen + Manipulation) | Fertigteil-Kiste; Roboter legt Werkstücke ab |
| `shelf_zone` | ≤ 0,3 m/s | Ja (Laufen + Manipulation) | Induktor-Regal für Werkzeugwechsel; geringe Geschwindigkeit für Genauigkeit |

**Station → Zone Mapping** (`config/stations.yaml`):
```
home           → transit
part_storage   → storage_zone
machine        → machine_zone
dropoff_box    → dropoff_zone
inductor_shelf → shelf_zone
```

Diese Geschwindigkeits-Schwellwerte sind **Platzhalter** und müssen bei der Risikobeurteilung mit dem
integrator und Safety-Ingenieur konkretisiert werden (Bremsweg-Berechnung, Maschinengeometrie, reale
Personenschutz-Anforderungen).

## 5. Reaktionsmatrix: Ereignisse und Reaktionen

| Ereignis | Hardwired-Reaktion (Sicherheits-SPS) | Funktionale Reaktion (h2_loader) |
|----------|--------------------------------------|----------------------------------|
| **Person dringt in Schutzfeld ein** | Sofort Bremsgruppen aktivieren, alle Bewegungen stoppen, Sperre-Magnete sperren | SafetySupervisor liest `safeZoneClear=0`, blockiert neue Bewegungsbefehle; `JobRunner` fährt recover (Greifer öffnen) |
| **Not-Halt (E-Stop) betätigt** | Zweikanalig, alle Achsen + Locomon-Sperren, Druck weg, Not-Halt-Kreis offen | SafetySupervisor liest `estopFromPlc=1`, blockiert Bewegungen; JobRunner quittiert Fehler, wartet auf Reset |
| **robotEnable-Signal weg (SPS schaltet aus)** | Optional zusätzliche Hardwire-Sperre; Haupteffekt über OPC-UA | SafetySupervisor liest `robotEnable=0`, blockiert Bewegungen; Ablauf pausiert |
| **Heartbeat-Timeout (PLC sendet 5s keinen Heartbeat)** | Optional SPS-interner Watchdog-Auslöser | SafetySupervisor in `H2HandshakeClient.is_plc_alive()` erkennt Timeout → `SafetySupervisor.is_safe()=False` → Bewegungen blockiert |
| **Zone ist belegt (andere Maschine lädt, Mensch im Bereich)** | Hardwired Sensor-Signal zur SPS | SafetySupervisor fragt OPC-UA-Spiegel ab; wenn `safeZoneClear=0`, blockt |
| **Roboter droht zu stürzen / Stabilitätsverlust** | Nicht in dieser Software realisierbar; Unitrees Onboard-Regler (PC1) stabilisiert oder der Roboter fällt | H2-Onboard-Regler (PC1, Unitree proprietär) kümmert sich; Folge-Unfall ist Faktum; Hardware-Eigenschaft des Systems (Schwerpunkt, Beinfeder-Stärke) |

## 6. Humanoid-spezifische Gefahren

Der H2 PLUS ist ein laufender humanoider Roboter mit folgenden Eigenschaften:
- **Masse:** ~70 kg
- **Höhe:** ~1,8 m
- **Bewegungsart:** Gangarten (Walk, Trot, Gallop — auf dem Onboard-Regler PC1 implementiert)

### 6.1 Sturzgefahr

Ein laufender 1,8-m-Roboter mit 70 kg kann **stürzen**. Ursachen:
- Ungleichmäßiger Untergrund, Hindernisse im Korridor
- Zu aggressive Kurve / Geschwindigkeit für das Gelände
- Rutschen auf glattem Boden
- Onboard-Regler-Fehler oder Hardwarefehler

**Wer behandelt das:**
- **Unitree Onboard-Regler (PC1):** Stabilisierungs-Algorithmen, Schwerpunkt-Kontrolle, Bein-Aktuator-Feuerung
  (proprietär, sperrbar auf dem Gerät, **nicht über diese Software änderbar**)
- **H2-Hardware:** Beinfeder-Steifigkeit, Schwerpunkt-Geometrie
- **Umgebung:** Ebener, unbehinderter Boden im transit-Bereich

**Software-Beitrag (h2_loader):** Begrenzte Geschwindigkeiten pro Zone, Vermeidung von Hindernissen (Sensor-Input),
Sicherheits-Zonen-Freigabe vor der Bewegung. Bei erkanntem Sturz (z.B. aus Vision/IMU-Daten — aktuell nicht implementiert):
Sofort Bewegung stoppen, Greifer öffnen, Zustand spiegeln.

**Konsequenz:** Ein Sturz ist nicht präventabel durch diese Software allein. Die Risikobeurteilung muss
ein Fallmatten-System, Schutzzonen-Planung (keine Treppen, keine scharfen Kanten im Korridor) oder akzeptable
Resiko-Klasse („Sturz eines Roboters in der Nähe ist ok, da kein Mensch anwesend") vorsehen.

### 6.2 Aufprall-Gefahr (fahrender Roboter → Person/Ausrüstung)

Ein fahrender Roboter mit 70 kg und Geschwindigkeiten bis 0,8 m/s kann eine Person verletzen, wenn er gegen sie fährt.
**Prävention:** Schutzfeld/Lichtgitter an der Zonengrenze + hardwired Stopp. Software-Prävention: Geschwindigkeits-Limits,
Bereichsfreigabe vor Fahrt. Aber kein Hindernis-Ausweichen in der aktuellen Version (neues Backend nötig).

## 7. Funktionaler SafetySupervisor (Software-Schicht)

Die Klasse `SafetySupervisor` in `core/safety.py` ist **eine rein funktionale Freigabe-Logik**, kein Sicherheitsschutz.

### 7.1 Prüfungen

```python
class SafetySupervisor:
    def is_safe(self) -> bool:
        """
        Liefert True, wenn die funktionale Seite die Bewegung freigibt.
        - Ist die OPC-UA-Verbindung aktiv? (Heartbeat-Check)
        - Ist robotEnable von der SPS aktiv?
        - Ist safeZoneClear (Zone ist frei)?
        - Ist estopFromPlc == 0 (kein Not-Halt)?
        """
        return (
            self.plc_client.is_plc_alive() and
            self.plc_client.robot_enable and
            self.plc_client.safe_zone_clear and
            not self.plc_client.estop_from_plc
        )
    
    def is_zone_clear(self, station: str) -> bool:
        """Abfrage der OPC-UA-Spiegel: ist Zone frei?"""
        return self.plc_client.safe_zone_clear
    
    def max_speed_for_station(self, station: str) -> float:
        """Liefert max. Geschwindigkeit für Station aus config/stations.yaml."""
        ...
    
    def allow_move_to(self, target_station: str) -> bool:
        """Kombiniert: ist_safe() + is_zone_clear(target)."""
        return self.is_safe() and self.is_zone_clear(target_station)
```

### 7.2 Integration in den Ablauf

```python
# core/job_runner.py
def step(self) -> JobOutcome | None:
    self.tick_heartbeat()
    job = self.poll_job()
    if not job:
        return None
    
    # === FUNKTIONALE SICHERHEITSPRÜFUNG ===
    if not self.supervisor.is_safe():
        # Funktional blockiert; Real-Hardware spricht auf hardwired Signale an
        return self.finish_job(JobResult.NOK)
    
    self.accept_job(job)
    try:
        self.set_robot_in_machine(True)
        skill = self.build_skill(job)
        skill.execute()  # Skill nutzt Locomotion/Motion/Gripper über deren Interfaces
        # Locomotion sieht sich den max_speed_for_station an
        self.finish_job(JobResult.OK)
    except Exception:
        skill.recover()
        self.finish_job(JobResult.NOK)
    finally:
        self.set_robot_in_machine(False)
```

### 7.3 Sicherheits-begrenzte Locomotion

```python
# hal/locomotion/onboard_locomotion.py
class OnboardLocomotion:
    def move_to(self, station: str) -> None:
        max_speed = self.config.station(station).max_speed  # aus config/stations.yaml
        # Unitree SDK-Befehl mit dieser Geschwindigkeit
        self.sdk.navigate_to(
            target=self.config.station(station).position,
            speed=max_speed
        )
```

**Wichtig:** Der `OnboardLocomotion` nutzt den bordeigenen Unitree-Regler (PC1 auf dem H2). Dieser wird
via SDK kommandiert; die Geschwindigkeits-Limits sind funktional. **Der echte Schutz vor Sturz/Stabilitätsverlust
liegt im Unitree-Regler und der Hardware, nicht in dieser Software.**

## 8. Normativer Rahmen (Orientierung für Risikobeurteilung)

Diese Richtlinien sind **nicht prescriptiv**, sondern geben den Kontext für eine Risikobeurteilung vor:

- **ISO 12100:2010** — Maschinensicherheit; Risikobeurteilung und Risikominderung (Fundament).
  Gefordert: Analyse der Gefahren (Sturz, Aufprall, Quetschung), Risiko-Bewertung (Schweregrad × Häufigkeit),
  Maßnahmen-Auswahl.

- **ISO 10218-1:2011** — Industrieroboter — Sicherheit. Teil 1: Allgemeine Anforderungen.
  Relevante Aspekte: Stillstand, Not-Halt, Sicherheits-Druckluft/Hydraulik, Bewegungsgrenzen.

- **ISO 10218-2:2011** — Industrieroboter — Sicherheit. Teil 2: Systeme und Integration.
  Relevant für Systemintegration: Safety-SPS, Peripherie (Greifer, Ventile), Schutzzonen.

- **ISO/TS 15066:2016** — Kollaborative Roboter — Sicherheit (nur Referenz; hier keine Ko-Präsenz).
  Definiert Kollaborations-Kriterien; im getrennten Betrieb nicht anwendbar.

- **ISO 3691-4:2020** — Fahrerlose Flurförderzeuge und ihre Systeme — Sicherheit.
  **Sinngemäß anwendbar** auf die Mobilitäts-Komponente (Locomotion): Bereichsüberwachung, Hinderniserkennung,
  Geschwindigkeit in Zonen.

- **ISO 13849-1:2015** — Maschinensicherheit; Sicherheitsbezogene Teile von Steuerungssystemen. Allgemeines
  Gestaltungsprinzipien (Performance Level / PL; Safety Integrity Level / SIL).
  Feststellung: Die hardwired Safety-SPS muss mindestens **PL d** (ISO 13849-1) oder **SIL 2** (IEC 62061) erreichen.
  Der funktionale h2_loader Supervisor ist **nicht sicherheitsgerichtet** und trägt zu keinem PL/SIL bei.

- **IEC 62061:2021** — Funktionale Sicherheit von Sicherheitssteuerungssystemen.
  Weitergehend als ISO 13849; für Systeme mit höheren Anforderungen (z.B. bewegliche Maschinen in Ko-Präsenz).

- **EN ISO 13855:2010** — Anordnung von Schutzeinrichtungen hinsichtlich ihrer Zustängigkeit und Annäherungsgeschwindigkeit.
  Auslegung der Lichtgitter/Schutzfelder (Erfassungsbereich, Sicherheitsabstände, Annäherungsgeschwindigkeit).

**Klarstellung:** Für humanoide Industrieroboter gibt es **keine produktspezifische Normenreihe** (im Gegensatz zu
Gelenkrobotern mit ISO 10218). Die oben genannten Normen sind die Grundlage. Eine vollständige **Risikobeurteilung
nach ISO 12100** ist notwendig und **Aufgabe des Integrators / Anwenders**; diese Dokumentation ersetzt sie nicht.

## 9. Offene Punkte & nächste Schritte

1. **Risikobeurteilung nach ISO 12100**
   - Durchführung durch qualifizierten Safety-Ingenieur mit Integrator + Anwender.
   - Feststellung: welche Gefahren (Sturz, Aufprall, Quetschung, …) sind relevant?
   - Risiko-Klasse pro Gefahr (Schweregrad × Häufigkeit).
   - Maßnahmen-Auswahl (Konstruktion, Sicherheits-SPS, Sensorik, Administrative Maßnahmen).

2. **Auswahl und Anordnung von Schutzeinrichtungen**
   - Art und Position von Lichtgitter/Schutzfeld (nach EN ISO 13855).
   - Sicherheitsabstände (Auslöseabstand, Anhaltestrecke des Roboters).
   - Sicherheits-SPS Spezifikation und Beschaffung.

3. **Validierung der Geschwindigkeits-Limits**
   - Fahrt-Tests in den Zonen mit realen Bremsparametern.
   - Verifizierung: Kann der Roboter aus der Höchstgeschwindigkeit vor ein Hindernis bremsen?

4. **Implementierung des Sturz-Detektors (fakultativ)**
   - IMU-basierte Detektion (H2 hat IMU onboard).
   - Optional: Machine-Learning basierte Stabilitäts-Vorhersage.
   - Fallback: Rückkehr zu sicherer Pose, Alarm.

5. **Inbetriebnahme-Validierung**
   - Alle Sicherheits-Schleifen testen (E-Stop, Schutzfeld, Not-Halt, Heartbeat-Ausfall).
   - Schulung des Bedien-Personals.
   - TÜV-Abnehme oder gleichwertige Zertifizierung (je nach lokalen Anforderungen).

6. **Dokumentation des zertifizierten Systems**
   - Technische Dateiblätter der Schutzeinrichtungen.
   - Sicherheits-SPS-Programm (TIA Portal, mit Funktionales Diagramm der Sicherheitslogik).
   - Test-Protokolle (Validierung aller Sicherheitsfunktionen).
   - Betriebsanleitung mit Sicherheitskapitel.

---

**Gültig ab:** 2026-06-29  
**Nächste Überprüfung:** Nach Inbetriebnahme + Risikobeurteilung
