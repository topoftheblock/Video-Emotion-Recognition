# DB-Export: Schema-Änderungen und Export-Regeln

Konsolidierte Entscheidungen für den Export der UIMA-Pipeline-Ergebnisse
(WhisperX / VideoID / PersonLinking / Emotion) in das SQL-Schema.

## Datenbank-Schema-Änderungen

1. **`Model`** (model_id, name, version, source) — nur für Embeddings; FK
   ausschließlich von den Embedding-Tabellen. In `source` die volle Kette
   (Repo@Commit, Original-Projekt, Feature-Parametrisierung — z. B. bei
   CAM++: 16 kHz mono, 80-dim Fbank), da sie Teil der
   Vektorraum-Identität ist. HF-Revision im Preloader auf Commit-SHA
   pinnen, nicht `main`.

2. **Embeddings: zwei Tabellen statt `BiometricEmbedding`** — die
   Dimensionen sind verschieden und pgvector braucht feste Dimension pro
   indizierter Spalte: `FaceEmbedding` (person_id, model_id, embedding
   vector(512), ArcFace w600k_r50) und `VoiceEmbedding` (person_id,
   model_id, embedding vector(192), CAM++ 3D-Speaker common-200k). Je
   eigener HNSW-Index (cosine); die `modality`-Spalte entfällt, die
   Tabellenwahl ersetzt sie. Ähnlichkeitssuche immer nur innerhalb einer
   Modality.

3. **`Segment`** (segment_id, video_id, kind `'shot' | 'sentence'`,
   seg_index, start_time, end_time, begin, end, person_id) — eine Tabelle
   für zeitliche und textliche Einteilung. `begin/end` nullable: nur bei
   `kind='sentence'` gefüllt (Zeichen-Offsets), Shots haben nur Zeiten.
   `person_id` nullable: nur bei `kind='sentence'` gefüllt (der Sprecher,
   aus `speakerSegment.voice.person` — eine SpeakerSentence hat per
   Konstruktion genau einen Sprecher).

4. **`LinguisticToken`**: + FK `segment_id` (der Satz, zu dem das Token
   gehört; Zuordnung per Offset-Containment). **Kein eigenes `person_id`
   am Token** — der Sprecher ist eine Satz-Eigenschaft und wird über den
   Join `token → segment → person_id` abgefragt; Denormalisierung ans
   Token nur nachrüsten, falls diese Query messbar dominiert (billiges
   `UPDATE … FROM segment`), nie als zweite unabhängige Wahrheit pflegen.

5. **`Presence`**: Struktur unverändert — kein Segment-Verweis, keine
   confidence-Spalte. `begin/end` nullable: nur bei `modality='speech'`
   gefüllt, bei `visible` NULL.

6. **`Video`**: + `fps`, `width`, `height`. Keine Metadaten-/
   PipelineRun-Tabellen.

7. **`Person`**: + `match_score double` (nullable). Semantik: **eine Row
   pro Identity, auch ungematcht** (`global_person_id` bleibt null).

8. **`FaceDetection`/`PersonDetection`**: + `detection_score`.

9. **Nicht aufnehmen:** mouthOpen/frontality, SpeakingActivity,
   PresenceSource-Brücke, berechnete Spalten (Frame-Nummern an
   Speech-Rows, Text-Offsets an Video-Rows — Zeit↔Frame on-the-fly über
   fps, Text↔Zeit per Join).

## Regeln, die man beim Export kennen sollte

1. **Nur an Personen hängende Daten kommen rein.**
   `createUnmatchedPersons=true`, damit jede Identity eine Person-Row hat;
   `minScore` entscheidet nur über Zusammenführung, nie über Existenz. Was
   zu keiner Person führt (z. B. raumweite Video-Emotion), wird nicht
   exportiert.

2. **match_score parsen:** steht nur im Person-Label
   (`voice:…|face:…|score:0.84[|lip]`) — defensiv parsen (Regex
   `score:([0-9.]+)`, bei Nichtfund NULL statt Crash), das Format ist
   nicht typisiert.

3. **begin/end je View:** transcriptView = Zeichen-Offsets → DB-Spalten
   begin/end. Video-View = ms-Eigenkonvention (nur UIMA-Index-Sortierung)
   → ignorieren, DB-begin/end dort NULL. Zeiten immer aus
   `timeStart/timeEnd` (Sekunden).

4. **Track-Merge → Presence(visible):** beim Import verschmelzen — gleiche
   FaceIdentity, Track endet an Shot-Endgrenze, Folgetrack beginnt an
   Folge-Shot-Startgrenze, Lücke ≤ ε ≈ `2·frame_stride/fps`. Welche Tracks
   verschmolzen wurden, wird nicht gemerkt.

5. **Token-Alignment spaCy ↔ WhisperX:** zwei Tokenisierungen auf
   demselben Sofa-Text. Zeiten pro spaCy-Token per
   Zeichen-Offset-Overlap mit den DiarizedAudioTokens (Two-Pointer,
   O(n)): start_time = timeStart des ersten, end_time = timeEnd des
   letzten überlappenden; Interpunktion erbt die Zeit des Wirtsworts. Auf
   Token-Ebene nicht clippen.

6. **Satz-/Presence-Zeiten clippen:** benachbarte Sätze können sich durch
   geteilte WhisperX-Tokens zeitlich minimal überlappen
   (Projektionsartefakt). In Textreihenfolge `start = max(start, prevEnd)`
   mit Guard; `BaseEmotion(text)` übernimmt die geclippten Satz-Zeiten
   (nicht neu rechnen).

7. **Views nicht verwechseln:** Audio-Seite (SpeakerSegment, Sentences,
   Text-/Audio-Emotion) aus `transcriptView`, Video-Seite (Tracks,
   Detections, Video-Emotion) aus `_InitialView`.

8. **Offset-Integrität:** latenter Off-by-N im WhisperX-Container
   (Whitespace-only-Token mit Zeitdauer → Lua fügt Leerzeichen ein,
   Python zählt nicht mit → alle folgenden Offsets +1). Fix
   `if len(text) == 0: continue` beim geplanten Container-Neubau; im
   Exporter zusätzlich der Assertion-Check
   `sofa.substring(begin, end).equals(token.value)` pro Dokument.
