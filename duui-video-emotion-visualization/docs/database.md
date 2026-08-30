# Database schema

Written from `pgvector-db/schema.sql`, which is authoritative for what the
database actually contains.

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

Fourteen tables. Twelve are filled by the importer from a CAS; two are not.
[architecture.md](architecture.md) says which sub-project writes what.

### `videos`

One video: the file, and everything the CAS said about it.

Keyed by `video_id` (`BIGSERIAL`), and unique by `filename`. The filename is
what the importer matches on, so re-importing the same video updates one row
rather than adding a second.

`filename` is also the join to the video store: the webapp plays
`<video store>/<filename>`. `duration`, `fps`, `width` and `height` are
whatever the CAS recorded, and any of them may be NULL.

### `models`

One upstream annotation model, by name, version and source.

Keyed by `model_id` (`BIGSERIAL`), with a natural key of
`(name, version, source)` — corpus-wide rather than per video, because the
same model annotates every video.

That unique constraint is declared `NULLS NOT DISTINCT`, which is not the
Postgres default. Without it, a model that carries no version or source would
insert a fresh row on every import instead of matching the one it wrote last
time, since two NULLs would count as different values.

### `global_persons`

One real individual, appearing in one or more videos.

Keyed by `global_person_id` (`BIGSERIAL`). `real_name` is a place for a human
to put a name: the identity linker always inserts NULL, nothing else writes
the column, and the webapp shows whatever it finds there.

The table is emptied and rebuilt in full by each run of the identity linker,
so a `global_person_id` is not stable across runs.

### `persons`

One person as detected within a single video.

Keyed by `(video_id, person_id)`. `person_id` is the CAS's own id and means
nothing outside its video, which is why the pair is the key and why no other
table refers to a person by `person_id` alone.

| Column | What it is |
| --- | --- |
| `clip_label` | A display name for this person within the video, as the CAS gave it. Nullable; the webapp falls back to the id. |
| `audio_video_match_score` | The upstream pipeline's confidence that this person's face and voice belong together. Not this project's number. |
| `global_person_id` | The link into `global_persons`. Written only by the identity linker; the importer leaves it NULL. `ON DELETE SET NULL`, so clearing a global person unlinks its people rather than deleting them. |
| `global_person_match_score` | The distance behind that link. Also the linker's. |

### `segments`

One span of a video. The umbrella table for two kinds, told apart by `kind`:
`shot` for a camera shot, `sentence` for a transcript sentence. A `CHECK`
constraint allows nothing else.

Keyed by `(video_id, segment_id)`. Spans carry both a time range
(`start_time`, `end_time`) and a character range in the transcript
(`begin_offset`, `end_offset`); which pair is meaningful depends on the kind,
and either may be NULL.

`person_id` is the speaker, and is nullable — a shot segment has none. The
foreign key is `ON DELETE SET NULL (person_id)`, naming the column explicitly,
because `video_id` is half of the row's own identity and cannot be nulled.

### `linguistic_tokens`

One word of the transcript, with its part-of-speech tag and named-entity
label.

Keyed by `(video_id, token_id)`. `segment_id` links the token to its sentence
segment and is nullable, because the upstream annotation carries that link
only sometimes.

`word` is the token text. `pos_tag` and `ner_label` are the tags as the
pipeline produced them; this project defines neither vocabulary.

### `face_embeddings` and `voice_embeddings`

One vector identifying a person, by face or by voice. Two tables of the same
shape, differing in dimension: `VECTOR(512)` for faces, `VECTOR(192)` for
voices.

Keyed by `(video_id, embedding_id)`. `person_id` says whose it is; `model_id`
says what produced it, and is a single-column reference because models are
corpus-wide.

Both carry an HNSW index on `embedding` with `vector_cosine_ops`, the operator
class for pgvector's `<=>`. That is the distance the identity linker compares
with, and the reason this is a pgvector database rather than a plain Postgres
one.

### `presences`

One span during which a person is present in one modality: `visible` for on
screen, `speech` for speaking. A `CHECK` constraint allows nothing else.

Keyed by `(video_id, presence_id)`. A presence is a span; a detection is a
frame within one.

### `face_detections` and `person_detections`

One bounding box for one person at one frame — the face box and the body box
respectively. Two tables, identical in shape.

Keyed by `(video_id, detection_id)`. The box is `(x, y, w, h)` as `REAL`, in
whatever coordinates the pipeline used; the schema does not normalize them.
`frame_index` and `t_time` place it, and `detection_score` is the detector's
confidence.

Each row references both its presence and its person. Both are nullable, and
both cascade.

### `base_emotions`

One emotion reading: a person, a modality, a granularity, a span, and a
dimensional reading.

Keyed by `(video_id, emotion_id)`. `modality` is `audio`, `video` or `text`;
`granularity` is `frame`, `segment`, `sentence` or `shot`. Both are held by
`CHECK` constraints.

`person_id` is nullable in every modality: a reading the pipeline could not
attribute to a person still belongs to its video.

`valence`, `arousal` and `dominance` are the dimensional reading, and
`dominant_label` the single label the model settled on. Which of those are
filled depends on the modality — a text reading has no frame and no box, and
carries only per-label scores. See [glossary.md](glossary.md#emotion-score)
for why the labels are not comparable across modalities and the dimensional
values are.

### `emotion_scores`

One `(label, score)` pair belonging to one base emotion: the full
distribution behind that row's `dominant_label`.

**The one table not keyed the way the others are.** The importer takes no
CAS id for a score, so the key is a surrogate `score_id` (`BIGSERIAL`), and
`UNIQUE (video_id, emotion_id, label)` carries the actual identity — which is
also what makes re-importing a video's scores idempotent. The reference back
to `base_emotions` is composite like every other.

A base emotion holds one row here per label in its model's inventory, so this
is by far the largest table.

### `job_runs`

One execution of a job: what it is, how it is going, and whether it is still
alive.

Keyed by `job_run_id` (`BIGSERIAL`). `job` names the kind of work, `status`
and `phase` where it has got to, `progress_current` and `progress_total` how
far. `started_at`, `heartbeat_at` and `finished_at` are `TIMESTAMPTZ`.

Two things make this table unlike the rest:

- **It is not derived from a CAS**, and has no `video_id`. It is the channel
  the jobs report progress on and the webapp reads — see
  [architecture.md](architecture.md).
- **Its DDL is repeated outside this file**, as `CREATE TABLE IF NOT EXISTS`
  in the three services that read or write it, because `schema.sql` runs only
  on an empty data directory. The four copies are identical and must stay so.

It is created `WITH (fillfactor = 70)`. The heartbeat rewrites one row roughly
once a second for the length of a run, and free space on the page is what
keeps those updates from leaving a dead tuple and a new index entry behind
each time.

## Indexes

Beyond the primary keys and unique constraints, `schema.sql` declares fifteen
indexes, all `IF NOT EXISTS`. None is required for correctness.

- **Two HNSW vector indexes**, on `face_embeddings.embedding` and
  `voice_embeddings.embedding`, described above.
- **Four supporting indexes** for queries that scan by video and then narrow:
  `base_emotions (video_id, modality)`, `segments (video_id, kind)`, and the
  two embedding tables by `(video_id, person_id)`.
- **Eight on the referencing side of a composite foreign key.** Postgres
  indexes the referenced side automatically and not this one, so without them
  a cascade that deletes by person or by presence has to scan. That is not a
  rare path: `--on-existing replace` deletes a whole video's subtree on every
  re-import.
- **One on `job_runs (job, started_at DESC)`**. Lookups against that table
  filter either on `job` — a starting job closing out a stale row of its own
  kind — or on `status`, and the index serves the first.

## Known data properties

Things that hold whatever is loaded, and that a query has to allow for.

- **An `xmi:id` is unique only within its own document.** The same value names
  unrelated rows in different videos, which is what the composite keys are
  for.
- **Almost every column is nullable.** The only `NOT NULL` columns are the
  key columns, `videos.filename`, and four of `job_runs`: `job`, `status`,
  `started_at` and `heartbeat_at`. The importer writes what the CAS carries
  and leaves the rest NULL rather than inventing a value, so a missing
  `person_id`, timestamp or box is a normal state and not a defect.
- **`person_id` is nullable everywhere it is a reference.** It is `NOT NULL`
  only in `persons`, where it is half the key. An annotation the pipeline
  could not attribute to a person is still stored against its video.
- **Emotion label vocabularies are model-native and differ by modality**, and
  `dominant_label` can be `<unk>` or empty. Compare across modalities on
  valence, arousal and dominance, never on labels. See
  [glossary.md](glossary.md#emotion-score).
- **Deleting a video deletes everything under it.** Every CAS-derived table
  cascades from `videos`. `models` and `global_persons` do not, being
  corpus-wide.
