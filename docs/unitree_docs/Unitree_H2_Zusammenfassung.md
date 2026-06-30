# Zusammenfassung: Unitree H2 (inkl. H2 EDU)

Hinweis: In der Unitree-Dokumentation und auf der Produktseite gibt es kein
eigenes Modell "H2 Plus". Gelistete Humanoide: H1, G1, H2, R1, G1-D.
Vom H2 existieren zwei Varianten: Standard "H2" und "H2 EDU" (freigeschaltet
fuer Eigenentwicklung / Secondary Development).
Quelle: support.unitree.com (H2 SDK Development Guide) + unitree.com/H2

## Aufbau & Freiheitsgrade (DoF)
- Insgesamt 31 DoF, angetrieben von 31 Gelenkmotoren.
- Pro Arm 7 DoF (3 Schulter, 2 Ellbogen, 2 Handgelenk).
- Pro Bein 6 DoF (3 Huefte, 1 Knie, 2 Knoechel).
- Taille/Huefte 3 DoF, Kopf 2 DoF.
- Knoechel und Taille nutzen einen Parallelmechanismus mit zwei Steuermodi (PR und AB).

## Technische Eckdaten (Produktseite)
- Hoehe/Breite/Tiefe (Stand): 1820 x 456 x 218 mm
- Gewicht: ca. 70 kg (mit Akku)
- Material: Flugzeug-Aluminium, Titanlegierung, hochfeste Kunststoffe
- Max. Drehmoment: Armgelenk 120 N.m, Beingelenk 360 N.m
- Arm-Nutzlast: Spitze ~15 kg, Nenn ~7 kg
- Akku: 15 Ah (0,972 kWh), max. 75,6 V, Laufzeit ca. 3 h, Schnellwechsel
- Sensorik: humanoide Binokular-Weitwinkelkamera, Mikrofon-Array, Lautsprecher
- Konnektivitaet: WiFi 6, Bluetooth 5.2
- Bionischer Kopf mit Gesichtszuegen

## H2 vs. H2 EDU - wichtigste Unterschiede
- Preis: Standard-H2 = 29.900 USD; EDU = auf Anfrage
- Secondary Development: nur EDU
- Dexterous Hand (geschickte Haende): nur EDU (mehrere Modelloptionen)
- Garantie: Standard 8 Monate / EDU 12 Monate
- EDU kann High-Power-Rechenmodule aufnehmen (z. B. Jetson Thor)

## Onboard-Computer
- Standard: 1 Motion Control Unit (PC1, Intel Core i5).
- Optional: 1-3 Development Computing Units (PC2/PC3/PC4, Intel Core i7 bzw. Jetson Thor).
- PC1 ist ausschliesslich fuer Unitrees Motion-Control reserviert, nicht offen.
- IP-Adressen: PC2/3/4 = 192.168.123.162/163/164; Mainboard = 192.168.123.161.
- Standard-Login: Benutzer "unitree", Passwort "Unitree0408"
  (aeltere Versionen: "Unitree#24226"; Entwicklungseinheit teils "123").

## Elektrische Schnittstellen (Rueckseite)
- Mehrere Type-C USB-3.0-Ports
- GMSL-Videoeingang
- 2x RJ45 Gigabit-Ethernet (1000BASE-T)
- GXT30-Stromanschluesse (12V/24V/Batterie mit 485- bzw. CAN-Kommunikation)
- 2x Board-to-Wire-Anschluesse fuer geschickte Haende (RS485 + USB 2.0)

## SDK & Kommunikation
- Entwicklung mit unitree_sdk2 (C++; auch Python- und ROS2-SDK verfuegbar),
  Kapselung ueber DDS.
- Zwei Kommunikationsmuster:
  - Publish/Subscribe (kontinuierliche/hochfrequente Daten)
  - Request/Response (niederfrequent / Funktionsumschaltung, API- oder
    Function-Call mit UUID-Zuordnung)
- DDS ist ROS2-kompatibel (Cyclone DDS 0.10.2).
- Wichtige Topics: rt/lowstate (Status: IMU, Motoren), rt/lowcmd (Low-Level-Steuerung).
- IDL-Strukturen: LowCmd_, LowState_, IMUState_, MotorCmd_, MotorState_.
- Hinweise: GST-Videostreaming wird aktuell noch nicht unterstuetzt;
  Cloud-Anbindung (MQTT, WebRTC, HTTP) nur nach Nutzerfreigabe.

## Steuerung & Betriebsmodi (Fernbedienung)
- Modi: Zero-Torque, Damping, Ready, Motion, Continuous Walking, Standing, Debug.
- Debug-Modus fuer SDK-Entwicklung:
  - aktivieren: L2 + R2
  - bestaetigen: L2 + A
  - Notfall (Damping): L2 + B
- Hintergrund: Beim Einschalten startet automatisch das Motion-Control-Programm
  und sendet Zero-Velocity-Befehle. Ohne Debug-Modus -> Befehlskonflikte und Zittern.
- Fernbedienung liefert 40 Byte Rohdaten (zwei Joysticks x/y im Bereich -1,0..1,0
  plus Tastenbelegung ueber xRockerBtnDataStruct).

## Entwicklungs-Setup (Quick Development)
- Empfohlen: Ubuntu 20.04/22.04 mit ROS2 Foxy/Humble; nur Linux (kein Windows/macOS).
- SDK von GitHub klonen (unitree_sdk2), Build mit cmake / make.
- Verbindung per Ethernet zum Schulter-RJ45-Port; eigene IP manuell setzen
  (z. B. 192.168.123.99); Test mit: ping 192.168.123.161
- Beispiel-Programm: ./h2_ankle_swing_example <network_interface>
- Ressourcen: URDF-Dateien und vereinfachtes STEP-Modell auf Unitrees GitHub.

## Hinweise fuer Demos/Videos
- Kniegelenke moeglichst gestreckt halten.
- Schrittfrequenz reduzieren (kein Auf-der-Stelle-Treten).
- Fuesse eng zusammen, ohne Spreizen.
- Empfehlung: eigenes Labor-Logo in Forschungsvideos zeigen.
