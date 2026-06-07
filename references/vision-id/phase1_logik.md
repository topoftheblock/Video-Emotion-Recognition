# Phase 1 — Logik & Methodik (knapp)

## Ablauf pro Frame (ein gemeinsamer Durchlauf, nicht drei Phasen)

1. **Personen-Detektion + Tracking.** YOLO detektiert Körper-Boxen. ByteTrack
   verkettet sie sofort mit den Boxen der Vorframes zu Tracks und vergibt die
   Track-ID. Jede Box → `PersonDetection`, direkt an ihren Track gehängt.
2. **Gesichts-Detektion + Zuordnung.** Im selben Frame läuft InsightFace (SCRFD)
   übers ganze Bild. Jedes Gesicht wird gefiltert und dann dem Track zugeordnet,
   dessen Personen-Box es enthält (Box-Containment). Überlebt es → `FaceDetection`
   + ArcFace-Embedding, an den Track gehängt.

Tracker **resettet an jeder Shot-Grenze** → Track-IDs sind shot-lokal.

## Was verworfen wird

- **PersonDetections:** nichts wird nachträglich gelöscht. Nur was ByteTrack gar
  keine ID gibt (unbestätigte Kurz-Erscheinungen), wird nicht gespeichert — das ist
  Tracker-intern, kein expliziter Filter.
- **FaceDetections:** verworfen, wenn (a) Gesicht zu klein (`min_face_frac`) oder zu
  unsicher (`min_det_score`), oder (b) in *keiner* Personen-Box → keine Zuordnung.

## Konstante ID über Shots — nur übers Gesicht

Da der Tracker an jedem Schnitt resettet, sind Track-IDs nur innerhalb eines Shots
gültig. Die **einzige Brücke zwischen Shots sind die ArcFace-Embeddings**, die
geclustert werden. Folge: **kein Gesicht → keine clip-weite Identität (P-ID).** Ein
Track ohne verwertbares Gesicht (z. B. Weitwinkel-Totale) bleibt anonym.

Das ist gewollt: relevante Personen (Redner:in, Gäste) erscheinen in Nahaufnahme →
dort sind Gesichter groß → dort klappt die Identität. Körper-Re-ID über Shots ist
*nicht* Teil von Phase 1.

## Embedding-Aggregation pro Track

Während des Laufs sammelt jeder Track `[(frontality, embedding), …]` aus seinen
Gesichtern. Aggregiert wird erst beim Clustering, in drei Schritten:

1. **Frontalste wählen:** nach Frontalität (Nase zentriert zwischen den Augen, aus
   den 5 SCRFD-Landmarks) sortieren, die besten `samples_per_track` (Default 5) nehmen.
   → filtert wegdrehende/Halbprofil-Frames, die ArcFace verrauschen.
2. **Mitteln:** elementweiser Mittelwert dieser Top-Embeddings → ein Vektor pro Track.
3. **Renormalisieren (L2):** Mittelung kürzt den Vektor; für die Cosine-Distanz muss er
   wieder Länge 1 haben.

Ergebnis: **ein** Repräsentativ-Embedding je Track. Diese Track-Vektoren (nicht die
einzelnen Frame-Embeddings) gehen ins **Agglomerative Clustering** (cosine,
`distance_threshold`). Ein Cluster = eine Person → `FaceIdentity`; alle Tracks im
Cluster erhalten dieselbe P-ID.

Warum so: Aggregation auf Track-Ebene ist robuster (ein schlechter Frame kann den
Track nicht mehr fehlleiten) und viel schneller (Dutzende Track-Vektoren statt
Tausende Frame-Vektoren). Mittel der frontalsten Crops ist die pragmatische Wahl;
Alternative wäre der Medoid.

## Stellschrauben

| Parameter | Wirkung |
|-----------|---------|
| `min_face_frac` | höher → nur große/nahe Gesichter, Publikum fällt raus |
| `distance_threshold` | kleiner → strenger, mehr Identitäten; größer → mehr Tracks fallen zusammen |
| `samples_per_track` | höher → stabileres Track-Embedding bei viel Kopfbewegung |
