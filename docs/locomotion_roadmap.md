# Locomotion-Roadmap: vom flachen Laufen zum menschenähnlichen Bewegen

Stand 2026-07-07. Ergänzt `docs/locomotion_training.md` (G1→H2-Strategie) und ADR-0008
(RL-Policy als Locomotion-Backend). Bewegungs-/Gehfähigkeiten des Unitree H2, trainiert per
RL in der Simulation (MuJoCo Playground / MJX + Brax PPO), Deployment im Twin und später real.

## Leitentscheidung Hardware

**Wir bleiben auf der vorhandenen Quadro M4000 (Maxwell, 8 GB) — kein GPU-Kauf.** Mehrtägige
Trainingsläufe sind akzeptiert. Das ganze Locomotion-Programm ist damit machbar, sofern:
- Beobachtungen **vektorbasiert** bleiben (Gelenkzustand + Höhenkarte + Referenzbewegung) —
  **keine Kamera-Pixel-RL** (die ginge auf der M4000 nicht; brauchen wir hier aber nicht).
- `num_envs` klein (512–1024 statt 4096–8192), längere Compile-Zeiten und Läufe von
  **mehreren Tagen bis ~1,5 Wochen** pro schwerer Fähigkeit eingeplant werden.

Der einzige Punkt, der später zwingend mehr GPU braucht, ist **GR00T-Fine-Tuning** (3-Mrd.-
Parameter-Greif-Modell, Arm-/Lade-Aufgabe) — das ist ein separater, einmaliger Cloud-/Miet-Job
und NICHT Teil dieses Locomotion-Programms. GR00T-Ausführung läuft ohnehin auf dem Jetson des Roboters.

## Stufenplan (Reihenfolge wie mit dem Anwender abgestimmt)

| # | Fähigkeit | Was zusätzlich nötig ist | M4000-Aufwand |
|---|---|---|---|
| 0 | **Flaches Laufen** | läuft (H2JoystickFlatTerrain, RL) | ~2 Tage (150 M) |
| 1 | **Treppen / unebenes Terrain** | Heightfield-Szene (rough + Treppenmuster), `task`-Auswahl; zunächst BLIND (propriozeptiv, wie G1-Rough) | ~4–10 Tage/Lauf |
| 2 | **Mit Bauteil (Zuladung)** | Domain-Randomisierung über Zusatzmasse + CoM-Versatz; Ganzkörper-Koordination | additiv, wenig extra |
| 3 | **Natürliches / menschenähnliches Gehen (+ Joggen)** | **AMP** (Adversarial Motion Priors) + **Referenz-Bewegungen** (Mocap, retargetet auf H2) | ~4–10 Tage/Lauf |
| 4 | **Springen / Hüpfen** | eigener Reward (Flugphase, Landung); **Hardware-Vorbehalt**: reale Aktuator-Spitzenmomente prüfen | mehrere Tage |
| 5 | **Perception-basierte Treppen** (optional, robuster) | Höhenkarten-Beobachtung (Terrain-Scan um die Füße) aus LiDAR/Tiefenbild | additiv |

## Wichtige technische Bausteine

- **Terrain (Stufe 1):** MuJoCo-`<hfield>` (Graustufen-PNG → Bodenhöhen). Rough = geglättetes
  Rauschen; Treppen = diskretes Stufenmuster. Boden-Geom bleibt `floor` (explizite Fuß-Pairs +
  Kontakt-Sensoren referenzieren es namentlich). `task_to_xml` wählt flat/rough/stairs.
  Erste Version **blind** (keine Terrain-Beobachtung) — genügt für niedrige Stufen, passt auf 8 GB.
- **Zuladung (Stufe 2):** im Domain-Randomizer je Env eine Zusatzmasse an einem Armglied +
  Schwerpunktversatz zufällig ziehen → Policy wird robust gegen „ich trage etwas".
- **Natürliche Bewegung (Stufe 3) — Datenstrategie:** Referenzbewegungen kommen aus
  **menschlichem Motion-Capture, retargetet auf H2s Kinematik** (freie Datensätze wie AMASS/CMU/
  LAFAN → 0 € Startkosten; eigener Mocap-Anzug nur bei Bedarf). **NICHT** durch „mit dem echten H2
  joggen" — solange er nicht joggen kann, gibt es nichts aufzuzeichnen, und Real-World-RL an einem
  Humanoiden ist unpraktikabel (zu viele Stürze). AMP-Diskriminator belohnt Bewegung „im Stil" der
  Referenz zusätzlich zum Aufgaben-Reward.
- **Wozu der echte H2 (EDU) wirklich dient:** (a) **Teleop-Manipulations-Demos** fürs Laden →
  Trainingsdaten für GR00T (ADR-0007); (b) **Sim-to-Real-Abgleich** (System-Identifikation), um die
  Sim-Parameter (Reibung, Masse, Aktuator-Verzögerung) genauer zu machen. Für die *Lauf*-Referenzen
  wird er nicht benötigt.

## Sim → Real (gilt für alle Stufen)

Trainiert wird in der Sim (Millionen Stürze kostenlos), dann Transfer. Offener Real-Schritt
(ADR-0008): Beobachtung aus echten Sensoren rekonstruieren (Obs-Bridge), Onboard-Inferenz auf dem
H2-Compute, zertifizierte Sicherheitstechnik + Risikobeurteilung vor jedem Reallauf. Der H2 EDU
bringt LiDAR + Tiefenkameras + Onboard-Compute bereits mit (Perception-HW muss nicht separat gekauft
werden).

## Arbeitsweise

Jede Stufe: Env/Reward/Terrain aufbauen (CPU, stört laufendes Training nicht) → wenn GPU frei →
mehrtägiger Lauf als systemd-Unit (entkoppelt, Checkpoints auf Platte) → Deploy über
`training/deploy/deploy_playground_policy.py` (Kennzahlen + VNC-Render). Locomotion (Beine, RL) und
Manipulation (Arme, GR00T/Teach-in) bleiben getrennte Policies.
