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

### Every CAS-derived row is keyed by `(video_id, xmi:id)`

An `xmi:id` identifies an annotation **within one CAS document**. It carries no
meaning across documents, so the same id names unrelated things in different
videos, and keying a table on the id alone would merge them. Ids do collide in
practice; `cas-to-postgres-importer` has a test for it,
`test_two_videos_can_hold_the_same_xmi_id`.

They are not small per-type counters restarting at 1 in each file, which is a
natural assumption and a wrong one — they are document-wide, and start wherever
that document's annotation numbering starts.

So:

- `video_id` is a surrogate key (`BIGSERIAL`), not anything from a CAS.
- Every CAS-derived table has `PRIMARY KEY (video_id, <its own xmi id>)`, and
  every foreign key between two of them carries both columns.
- `videos` is keyed for the importer by `filename`, the one identifier stable
  across re-imports and already the join key to the video store.

### The two exceptions

| Table | Why it is not scoped to a video |
| --- | --- |
| `models` | Corpus-wide. The same model annotates every video, so it has a natural key of `(name, version, source)` rather than a copy per video. |
| `global_persons` | Corpus-wide by definition, and its ids are assigned by the database rather than taken from any CAS. |

### `video_id` is not stable across a re-import

`--on-existing replace` deletes a video's row and inserts a new one, so the
`BIGSERIAL` advances and the video gets a **different** `video_id`. Anything
holding one — a bookmarked URL, a saved query, an exported result — will not
survive a replace. The video *file* is unaffected, because the video store is
keyed by `filename`.

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
