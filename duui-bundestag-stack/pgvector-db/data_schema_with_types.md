# Datenbank-Schema: DUUI Pipeline Export

Dieses Schema konsolidiert die Export-Regeln und Strukturen für die UIMA-Pipeline-Ergebnisse (WhisperX / VideoID / PersonLinking / Emotion).

> **This is the design document, not a description of the running
> database.** `pgvector-db/schema.sql` is the authoritative schema, and the
> importer follows it where the two differ. Known, deliberate
> divergences: the text offsets are called `begin_offset`/`end_offset`
> in the database (`END` is a reserved word in SQL); the single
> `Detection` type here is implemented as separate `face_detections`
> and `person_detections` tables; `segments` is also fed by
> `SpeakerSentence` (for `kind = 'sentence'`), not only by `Shot`; and
> text emotion comes from a second UIMA type not listed here
> (`org.texttechnologylab.annotation.Emotion`, GoEmotions-style — see
> `cas-to-postgres-importer/src/main/parsers/text_emotion.py`). Keep this file as
> the record of the intended design; correct the code, not the spec.
>
> **One divergence is load-bearing and worth stating here.** The "PK"
> columns below (`person_id`, `segment_id`, `emotion_id`, …) are the
> source document's own `xmi:id`, which is a *per-document* counter —
> every CAS restarts it at 1. In the database each of those is
> therefore only half of a composite primary key,
> `(video_id, <the id>)`, and every foreign key between them is two
> columns. Keying on the id alone merged nine files into a single
> video row in practice. `videos` itself is keyed by `filename`, and
> `models` by `(name, version, source)` since a model is corpus-wide.
> See `pgvector-db/schema.sql`'s identity note.

## Metadaten & Video Layer

**Video** (The Master File)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| video_id | bigint | PK | Unique ID of the video |
| filename | text | | Name of the video file (e.g., debate.mp4) |
| duration | double | | Total duration in seconds |
| processed_at | timestamp | | Processing timestamp of the DUUI pipeline |
| fps | double | | Frames per second |
| width | int | | Video width in pixels |
| height | int | | Video height in pixels |

**Model** (Embedding Provenance)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| model_id | bigint | PK | Unique ID of the model |
| name | text | | Model name (z. B. ArcFace, CAM++) |
| version | text | | Model version |
| source | text | | Volle Kette (Repo@Commit, Original-Projekt, Feature-Parametrisierung) |

---

## Text & Segmente

**Segment** (Zeitliche und textliche Einteilung)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| segment_id | bigint | PK | Unique ID of the segment |
| video_id | bigint | FK | Reference to the video |
| kind | text | | `'shot'` oder `'sentence'` |
| seg_index | int | | Fortlaufender Index des Segments |
| start_time | double | | Start time in seconds |
| end_time | double | | End time in seconds |
| begin | int | | Text-offset start (nullable, nur bei `'sentence'`) |
| end | int | | Text-offset end (nullable, nur bei `'sentence'`) |
| person_id | bigint | FK | Sprecher des Satzes (nullable, nur bei `'sentence'`) |

**LinguisticToken** (NLP Text Connection)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| token_id | bigint | PK | Unique ID of the word/token |
| video_id | bigint | FK | Reference to the video |
| segment_id | bigint | FK | Reference to the Segment (Satz-Zugehörigkeit) |
| start_time | double | | Start time of the spoken word |
| end_time | double | | End time of the spoken word |
| begin | int | | Text-offset start (in the transcribed text) |
| end | int | | Text-offset end |
| word | text | | The raw word (output from WhisperX / spaCy) |
| pos_tag | text | | Part-of-Speech Tag (e.g., NOUN, VERB) |
| ner_label | text | | Named Entity Recognition Label (e.g., PER, ORG) |

---

## Identity, Embeddings & Presence Layer

**GlobalPerson**

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| global_person_id | bigint | PK | Cross-video person (e.g., via global clustering) |
| real_name | text | | Real name of the person (if known) |

**Person**

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| person_id | bigint | PK | Unique ID of the person in the video (local) |
| video_id | bigint | FK | Reference to the video |
| global_person_id | bigint | FK | Reference to GlobalPerson (nullable, until assigned) |
| clip_label | text | | Local label (e.g., P8 / Speaker_01) |
| audio_video_match_score | double | | Import-pipeline confidence of the match (nullable, parsed from the CAS label, 0..1) |
| global_person_match_score | double | | Cross-video match distance: minimum cosine distance to this person's nearest lookalike in another video (0 = identical, 2 = opposite, lower = more confident). Computed by the global-identity job. |

**FaceEmbedding** (pgvector HNSW-Index: cosine)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| embedding_id | bigint | PK | Unique ID of the vector |
| person_id | bigint | FK | Assigned person (local) |
| model_id | bigint | FK | Reference to Model |
| embedding | vector(512) | | z. B. ArcFace w600k_r50 |

**VoiceEmbedding** (pgvector HNSW-Index: cosine)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| embedding_id | bigint | PK | Unique ID of the vector |
| person_id | bigint | FK | Assigned person (local) |
| model_id | bigint | FK | Reference to Model |
| embedding | vector(192) | | z. B. CAM++ 3D-Speaker common-200k |

**Presence** (Track-Merge Intervalle)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| presence_id | bigint | PK | Unique ID of the presence interval |
| person_id | bigint | FK | Present person (local) |
| video_id | bigint | FK | Reference to the video |
| modality | text | | `'visible'` oder `'speech'` |
| start_time | double | | Start time in seconds |
| end_time | double | | End time in seconds |
| begin | int | | Text-offset start (nullable, nur bei `'speech'`) |
| end | int | | Text-offset end (nullable, nur bei `'speech'`) |

**FaceDetection**

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| detection_id | bigint | PK | Unique ID of the face bounding box |
| presence_id | bigint | FK | Associated visibility interval |
| person_id | bigint | FK | Visible person (local) |
| video_id | bigint | FK | Reference to the video |
| frame_index | int | | Frame number |
| t_time | double | | Timestamp of the frame in seconds |
| x, y, w, h | real | | Box coordinates, normalized 0..1 |
| detection_score| double | | Confidence score of the detection |

**PersonDetection**

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| detection_id | bigint | PK | Unique ID of the person bounding box |
| presence_id | bigint | FK | Associated visibility interval |
| person_id | bigint | FK | Visible person (local) |
| video_id | bigint | FK | Reference to the video |
| frame_index | int | | Frame number |
| t_time | double | | Timestamp of the frame in seconds |
| x, y, w, h | real | | Box coordinates, normalized 0..1 |
| detection_score| double | | Confidence score of the detection |

---

## Emotion Layer

**BaseEmotion** (Starting point for raw data from containers)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| emotion_id | bigint | PK | Unique ID of the base emotion |
| person_id | bigint | FK | Assigned person (local) - Nur personenbezogene Daten! |
| video_id | bigint | FK | Reference to the video |
| modality | text | | `'audio'`, `'video'` oder `'text'` |
| granularity | text | | `'frame'`, `'segment'`, `'sentence'` oder `'shot'` |
| start_time | double | | Start time in seconds (bei Sätzen aus WhisperX geclippt) |
| end_time | double | | End time in seconds (bei Sätzen aus WhisperX geclippt) |
| begin | int | | Text-offset start (nullable, nur für text) |
| end | int | | Text-offset end (nullable, nur für text) |
| frame_index | int | | Frame number (nullable, nur für video-frame) |
| x, y, w, h | real | | Bounding box at frame granularity (nullable) |
| valence | double | | Valence [-1,1] |
| arousal | double | | Arousal [-1,1] |
| dominance | double | | Dominance [-1,1] (nur für audio) |
| dominant_label | text | | Strongest class (argmax) |

**EmotionScore** (Distribution for BaseEmotion)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| emotion_id | bigint | FK | Reference to BaseEmotion |
| label | text | | Emotion class (e.g., Happy, Sad, Neutral) |
| score | double | | Probability / Confidence |

**FusedEmotion** (Aggregated / Calculated Emotions)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| fused_id | bigint | PK | Unique ID of the fusion emotion |
| video_id | bigint | FK | Reference to the video |
| person_id | bigint | FK | Assigned person (nullable, e.g., for room-wide emotions) |
| fusion_method | text | | Method (e.g., cross-modal-attention) |
| target_modality | text | | `'multimodal'`, `'video-aggregated'` oder `'text-aggregated'` |
| start_time | double | | Start time of the fusion interval |
| end_time | double | | End time of the fusion interval |
| valence | double | | Calculated total valence |
| arousal | double | | Calculated total arousal |
| dominant_label | text | | Resulting strongest class |

**EmotionFusionReference** (n:m bridge for the origin of the fusion)

| Column | Type | Key | Description |
| :--- | :--- | :--- | :--- |
| fused_id | bigint | FK | Reference to FusedEmotion |
| source_emotion_id| bigint | FK | Reference to the source BaseEmotion |

---

## Type System to Database Mapping for Parser

### Video
- **Type System:** MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.type.MultimediaElement`
- **Features/Columns:** `video_id, filename, duration`

### Model
- **Type System:** MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.MetaData`
- **Features/Columns:** `model_id, name, version, source`

### Segment
- **Type System:** MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.video.Shot`
- **Features/Columns:** `segment_id, video_id, kind, seg_index, start_time, end_time`

### LinguisticToken
- **Type System:** IdentityEmotionTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.type.DiarizedAudioToken`
- **Features/Columns:** `token_id, video_id, segment_id, start_time, end_time, begin, end, word, pos_tag, ner_label`

### Person
- **Type System:** IdentityEmotionTypeSystem, MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.identity.Person`
- **Features/Columns:** `global_person_id, real_name, person_id, clip_label, audio_video_match_score, global_person_match_score`

### FaceEmbedding
- **Type System:** IdentityEmotionTypeSystem, MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.identity.FaceIdentity`
- **Features/Columns:** `embedding_id, person_id, model_id, embedding`

### VoiceEmbedding
- **Type System:** IdentityEmotionTypeSystem, MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.identity.VoiceIdentity`
- **Features/Columns:** `embedding_id, person_id, model_id, embedding`

### Presence
- **Type System:** IdentityEmotionTypeSystem, MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.video.PersonTrack`
- **Features/Columns:** `presence_id, person_id, video_id, modality, start_time, end_time`

### Detection
- **Type System:** IdentityEmotionTypeSystem, MultimodalIdentityTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.video.Detection`
- **Features/Columns:** `detection_id, presence_id, person_id, video_id, frame_index, t_time, x, y, w, h, detection_score`

### BaseEmotion
- **Type System:** EmotionTypeSystem, IdentityEmotionTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.emotion.Emotion`
- **Features/Columns:** `emotion_id, person_id, video_id, modality, granularity, start_time, end_time, frame_index, x, y, w, h, valence, arousal, dominance, dominant_label`

### EmotionScore
- **Type System:** EmotionTypeSystem, IdentityEmotionTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.emotion.EmotionScore`
- **Features/Columns:** `emotion_id, label, score`

### FusedEmotion
- **Type System:** EmotionTypeSystem, IdentityEmotionTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.emotion.Emotion`
- **Features/Columns:** `fused_id, video_id, person_id, fusion_method, target_modality, start_time, end_time, valence, arousal, dominant_label`

### EmotionFusionReference
- **Type System:** EmotionTypeSystem, IdentityEmotionTypeSystem
- **UIMA Type:** `org.texttechnologylab.annotation.emotion.Emotion`
- **Features/Columns:** `fused_id, source_emotion_id`

