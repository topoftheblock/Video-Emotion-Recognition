# Datenbank-Schema: DUUI Pipeline Export

Dieses Schema konsolidiert die Export-Regeln und Strukturen für die UIMA-Pipeline-Ergebnisse (WhisperX / VideoID / PersonLinking / Emotion).

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
| match_score | double | | Confidence of the match (nullable, aus Label geparst) |

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