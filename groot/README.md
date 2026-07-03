# GR00T-Vorbereitungsartefakte (ADR-0007)

Dieser Ordner enthält die Konfigurationsartefakte für das künftige GR00T-N1.7-
Fine-Tuning des H2-Laders als `NEW_EMBODIMENT`. Er liegt bewusst **außerhalb**
von `src/h2_loader/`, weil er das `gr00t`-Paket importiert, das nur auf dem
Training-Rig (Linux + CUDA) installiert ist — hier im Repo nicht ausführbar
und nicht Teil der Testsuite.

## Dateien

- **`h2_modality_config.py`** — Modality-Config für das H2-Embodiment, nach
  dem Muster `examples/SO100/so100_config.py` aus
  [NVIDIA/Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T). Registriert
  Video- (`head`/`wrist`), State-, Action- (rechter Arm 7 DoF + Greifer) und
  Language-Modalitäten für `EmbodimentTag.NEW_EMBODIMENT`.
- **`meta_modality.example.json`** — Beispiel für die `meta/modality.json`
  eines H2-Datensatzes: beschreibt, an welchen Indizes der flachen
  state-/action-Vektoren die einzelnen Modality-Keys liegen. Wird inhaltlich
  von `h2_loader.dataset.LerobotDatasetExporter.finalize()` erzeugt.

## Nutzung auf dem Training-Rig

1. `gr00t` installieren (Linux + CUDA, siehe `docs/groot_setup.md`).
2. `h2_modality_config.py` importieren (registriert die Config als Seiteneffekt)
   oder ihren Inhalt in die GR00T-Fine-Tune-Konfiguration übernehmen.
3. Den mit `LerobotDatasetExporter` erzeugten Datensatz (`meta/modality.json`
   muss zur registrierten Config passen) als Trainingsdatensatz einhängen.

Details zum Gesamtablauf: `docs/groot_setup.md` (technisches Setup) und
`docs/roadmap_groot.md` (Stufenplan, ADR-0007).
