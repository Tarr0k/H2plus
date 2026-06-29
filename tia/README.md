# TIA-Portal-UDTs: OPC-UA-Schnittstelle S7-1500 <-> Unitree H2-PLUS

UDT-Definitionen für die OPC-UA-Schnittstelle zwischen einer Siemens S7-1500 und einem
Unitree-H2-PLUS-Roboter, der als Maschinenlader an einer Induktionshärtemaschine arbeitet.

## Wofür die UDTs sind

Die Schnittstelle bündelt alle zwischen SPS und Roboter ausgetauschten Daten in einem
einzigen, klar strukturierten Datentyp. Das vereinfacht das Mapping auf OPC-UA-Knoten und
hält die NodeId-Pfade stabil.

| UDT | Richtung | Inhalt |
|---|---|---|
| `H2Control_UDT` | beidseitig | Heartbeat/Alive-Überwachung, Schnittstellenversion, Betriebsmodus |
| `H2PlcToRobot_UDT` | SPS -> H2 | Auftragsvorgabe + Maschinenzustand (Tür, Spannvorrichtung, Bearbeitung) |
| `H2RobotToPlc_UDT` | H2 -> SPS | Roboterzustand, Auftragsquittierung, Anforderungen an die Maschine |
| `H2Safety_UDT` | beidseitig | Funktionale Sicherheitsspiegel (NICHT sicherheitsgerichtet) |
| `H2Interface_UDT` | Container | fasst die vier obigen Teil-UDTs zusammen |

Die Vollspezifikation aller Member (Bedeutung, Wertebereiche, Handshake-Logik) steht in
[`docs/plc_interface.md`](../docs/plc_interface.md).

## Import in TIA Portal V20

Die Datei `udt/H2_Interface_UDTs.scl` enthält alle fünf `TYPE ... END_TYPE`-Blöcke in der
korrekten Reihenfolge (zuerst die vier Teil-UDTs, dann der Container — sonst schlägt die
Auflösung der Sub-UDT-Referenzen fehl).

### Variante A: Externe SCL-Quelle (manuell, ohne Openness)

1. In der Projektnavigation unter der CPU: **Externe Quellen** -> **Neue externe Quelle hinzufügen**.
2. `udt/H2_Interface_UDTs.scl` auswählen.
3. Rechtsklick auf die Quelle -> **Bausteine aus Quelle generieren**.
4. TIA erzeugt die fünf PLC-Datentypen unter **PLC-Datentypen**.

### Variante B: Über TIA Openness

1. SCL-Datei als externe Quelle hinzufügen
   (`PlcExternalSourceGroup.CreateFromFile(...)`).
2. Bausteine/Datentypen generieren
   (`PlcExternalSource.GenerateBlocksFromSource()`).

> Hinweis: Die `.scl`-Datei ist als UTF-8 gespeichert. Falls der Openness-Importer
> beim Einlesen abbricht, die Datei als **UTF-8 mit BOM** (CRLF-Zeilenenden) neu speichern.

## Datenbaustein anlegen

Einen globalen DB `"H2_Interface_DB"` mit genau einem Member anlegen:

```
H2_Interface_DB
  iface : "H2Interface_UDT"
```

Empfehlung: **optimierter Bausteinzugriff** aktiviert lassen.

## OPC-UA-Server aktivieren

1. CPU-Eigenschaften -> **OPC UA** -> **Server** -> **OPC-UA-Server aktivieren**.
2. Den DB `"H2_Interface_DB"` als **aus OPC UA erreichbar** markieren
   (DB-Eigenschaften -> Attribute -> *Aus OPC UA erreichbar*).
3. Bei optimiertem Zugriff einzelne Member ggf. zusätzlich über *Sichtbar im HMI/OPC UA*
   freigeben.

## NodeId-Schema

Die OPC-UA-NodeIds folgen dem String-Identifier-Schema des SIMATIC-Servers
(Namespace-Index `ns=3` für das Anwender-Adressraum-Modell der CPU):

```
ns=3;s="H2_Interface_DB"."iface"."control"."plcHeartbeat"
ns=3;s="H2_Interface_DB"."iface"."plcToRobot"."jobRequest"
ns=3;s="H2_Interface_DB"."iface"."robotToPlc"."robotInMachine"
ns=3;s="H2_Interface_DB"."iface"."safety"."robotEnable"
```

Allgemein:

```
ns=3;s="H2_Interface_DB"."iface".<bereich>.<member>
```

## Sicherheitshinweis (WICHTIG)

OPC UA ist hier **NICHT sicherheitsgerichtet**. Der `H2Safety_UDT` enthält nur
**funktionale Spiegel** der Sicherheitssignale zu Diagnose- und Verriegelungszwecken auf
Anwenderebene.

Der **echte Not-Halt** und alle sicherheitsgerichteten Funktionen müssen **hardwired**
über die Safety-SPS bzw. F-Signale (fehlersichere Ein-/Ausgänge) realisiert werden.
Die OPC-UA-Schnittstelle darf keine Safety-Funktion ersetzen.
