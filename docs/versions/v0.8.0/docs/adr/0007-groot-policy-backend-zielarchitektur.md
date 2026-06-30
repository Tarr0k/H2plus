# ADR-0007: GR00T N1.7 Policy-Backend als Zielarchitektur

- **Status:** Akzeptiert (Zielrichtung, Endstufe)
- **Datum:** 2026-06-30
- **Kontext-Quelle:** Anwender-Vorgabe; verifiziert gegen NVIDIA/Isaac-GR00T Doku, Unitree Repos (per API geprüft 2026-06-30)

## Kontext

Der Unitree H2-Lader lädt heute mittels **Teach-&-Replay** (ADR-0001): menschliche Positionen werden demonstriert, der Roboter fährt sie ab. Das funktioniert, ist aber nicht generalistisch — jede neue Aufgabe (anderer Induktor, andere Werkstückform) braucht neue Teach-Daten.

**Vision:** Eine **gelernte Manipulations-Policy** kann aus wenigen Demos verallgemeinern und adaptieren. NVIDIA **GR00T N1.7** ist ein Foundation Model dafür — ein Vision-Language-Action-Modell (~3B Parameter, Apache-2.0), das auf mehreren Roboter-Embodiments vortrainiert ist.

**Frage:** Sollen wir GR00T als strategisches Ziel festlegen für die Arm-Steuerung des H2-Laders?

## Entscheidung

Ja. **GR00T N1.7 wird das strategische Ziel-Backend** für Manipulations-Policies des H2-Laders.

### Implementierung

1. **PolicyInterface** (neu)  
   Führe ein abstraktes `PolicyInterface` mit Methode `predict(observation) → action` ein.
   Input: RGB-Beobachtung + Gelenkpositionen (Propriozeption).  
   Output: nächste Arm-Gelenkwinkel-Vektor.

2. **Zwei konkrete Backends**
   - `ScriptedPolicy`: der heutige Teach-&-Replay-Planner (v0.6.0). Bleibt Fallback.
   - `GrootPolicy`: GR00T N1.7 Fine-Tuned für H2 (Stufen 1–3, vgl. `docs/roadmap_groot.md`).

3. **Safety-Clamping**  
   Policy-Ausgaben werden vor Arm-SDK in jedem Schritt geclampt (Workspace, Velocity, Force-Grenzen).

4. **Unverändert**
   - Orchestrator + MotionPlannerInterface (ADR-0003)
   - SafetySupervisor + hardwired Safety (ADR-0005)
   - Locomotion, PLC-Handshake, Greifer-Steuerung

Der **Teach-in-Modus (ScriptedPolicy) bleibt Fallback**, falls GR00T ausfällt.

## Konsequenzen

### ➕ Positive Konsequenzen

- **Generalisierung:** Policy kann aus Demos auf neue Aufgaben verallgemeinern (neue Werkstückformen, neue Induktoren), ohne Scripting.
- **Adaptive Robustheit:** Foundation Model hat bereits Millionen Trajectories gesehen → schneller adaptiert als Teach-in von Null.
- **Architektur stabil:** Neue `PolicyInterface` ist minimal; Skills und Orchestrator ändern sich nicht.
- **Open-Source & Apache-2.0:** GR00T ist OSS; kein Vendor Lock-in; vollständige Kontrolle über Finetuning.
- **EDU-gerecht:** Jetson AGX Thor auf H2 EDU reicht für ~10,7 Hz TensorRT-Inferenz — passend für Manipulations-Regeltakt.

### ➖ Negative Konsequenzen & Aufwände

- **H2 ist NEW_EMBODIMENT:** Unitree H2 ist NICHT vorkonfiguriert in GR00T.  
  → Eigenes Fine-Tuning nötig (URDF, Modality-Config, Training).
- **Datenaufwand:** Teleop-Demonstrationen müssen gesammelt werden (Anzahl projekt-/aufgabenabhängig,
  noch festzulegen; GR00T-Beispiele nutzen kleine Demo-Datensätze, Unitree nennt für Imitation Learning
  grob 50–200 Episoden — gegen aktuelle Doku prüfen).  
  → Operateur-Schulung, Teleop-Setup (`xr_teleoperate`), Datenmanagement.
- **GPU-Aufwand:** Fine-Tuning braucht min. 1 GPU 40 GB+, empfohlen 4–8× H100/L40 (Full-Scale 8× RTX Pro
  6000/DGX). Trainingsdauer hängt von Datenmenge/Hardware ab (nicht belegt).  
  → Entweder Cluster-Zugang oder externe Cloud-Ressourcen.
- **Non-Determinismus:** Policy-Ausgaben sind stochastisch.  
  → Safety-Clamping ist Pflicht; Fehlerbehandlung muss robust sein.  
  → Kein "sicherheitsgerichtet" im Sinne von ISO 13849.
- **Zeitplan:** projektabhängig, noch festzulegen (Reihenfolge der Stufen siehe `docs/roadmap_groot.md`).  
  → Teach-in (ScriptedPolicy) muss v0.6.0+ parallel weiterlaufen und stabil sein.

### Limitations

- **Nicht Ganzkörper-Steuerung:** GR00T lernt Ganzkörper-Bewegung (inkl. Balance). Für den Lader: nur Arme relevant; Body-Balance ist durch den Onboard-Regler (PC1) abgedeckt. Wie man „Balance erhalten, nur Arme" kapselt, ist noch zu verifizieren (Gewichtungs-Masking).
- **Simulation-to-Reality-Lücke:** Validierung in Isaac Lab ist nötig; Real-World-Performance kann abweichen.
- **Abhängigkeit von Datenqualität:** Schlechte Teleop-Daten → schlechte Policy. Operateur-Training und Datenprüfung sind kritisch.

## Abnahmekriterien für künftige Stufen

1. **Stufe 1 erreicht:** Teleop-Datenerfassung abgeschlossen, Datensatz vorhanden und validiert.
2. **Stufe 2 erreicht:** Fine-Tuning-Lauf erfolgt, trainiertes Checkpoint existiert, Sim-Validierung zeigt akzeptable Erfolgsquote.
3. **Stufe 3 erreicht:** `PolicyInterface` + `GrootPolicy` implementiert, in h2_loader integriert, Safety-Clamping-Module (workspace, velocity, force) implementiert und getestet, Fallback-Logik zwischen `ScriptedPolicy` ↔ `GrootPolicy` funktional, Real-World-Tests durchgeführt.
4. **Dokumentation:** `docs/roadmap_groot.md` aktualisiert mit realen Erfahrungen aus jeder Stufe.

**Umsetzungsstand v0.8.0 (2026-06-30):** Der Policy-Seam ist angelegt — `policy/`-Paket mit
`PolicyInterface` (`predict(Observation)→Action`), `ScriptedPolicy` (Teach-in, deterministisch),
`GrootPolicy` (Stub → `NotImplementedError`), `SafeguardedPolicy` (Gelenk-Clamping) und `FallbackPolicy`
(groot→scripted). Skills nutzen die Policy, wenn gesetzt; `app.py --policy scripted|groot`. **Offen bleiben
Stufe 1–3** (Teleop-Daten, Fine-Tuning NEW_EMBODIMENT, Thor-Deployment + reale GR00T-Inferenz). `GrootPolicy`
enthält noch KEINE Inferenz.

## Abhängige ADRs & Dokumente

- **ADR-0001:** Teach-&-Replay (bleibt als ScriptedPolicy)
- **ADR-0003:** MotionPlannerInterface (wird nicht geändert; PolicyInterface sitzt darunter)
- **ADR-0005:** Sicherheitskonzept (Safety-Clamping, SafetySupervisor bleiben)
- **ADR-0006:** Schritt-Ebene auf UDT (unverändert)
- **docs/roadmap_groot.md:** Detaillierter Stufenplan, Hardware, Pipeline
- **docs/sdk_reference.md:** H2-Spezifika
- **docs/architecture.md:** Schichtenmodell

## Ausblick

Während der Implementierung wird die Weiterentwicklung von Teach-in (v0.6.0 → v1.0) parallel laufen.  
Langfristig: wenn `GrootPolicy` robust läuft, kann `ScriptedPolicy` zu reinem Fallback-Modus degradiert werden.

---

**Gültig ab:** 2026-06-30  
**Nächste Überprüfung:** Nach Abschluss von Stufe 1 (Teleop-Datenerfassung)
