# Database schema

Written from `pgvector-db/schema.sql`, which is authoritative for what the
database actually contains.

**This does not replace `pgvector-db/data_schema_with_types.md`.** That file is
a different artifact: the *design* mapping from UIMA CAS types to tables. The
two are complementary — it records what the pipeline export was specified to be,
this records what the database is. See the Phase 2 ledger for how far apart they
are.

> **Stub.** Written in Phase 7, from `schema.sql` only. Terminology follows
> [glossary.md](glossary.md).

## Conventions

<!-- Composite keys scoped by video_id; ON DELETE CASCADE; why person_id is not
     globally unique. -->

## Tables

<!-- One section per table: what one row represents, its key, and its
     non-obvious columns. Order: videos, models, global_persons, persons,
     segments, linguistic_tokens, face_embeddings, voice_embeddings, presences,
     face_detections, person_detections, base_emotions, emotion_scores,
     job_runs. -->

## Known data properties

<!-- Emotion labels are model-native and differ by modality; <unk> and empty
     dominant_label values exist. VAD is the cross-modality comparable axis.
     See glossary.md#emotion-score. -->
