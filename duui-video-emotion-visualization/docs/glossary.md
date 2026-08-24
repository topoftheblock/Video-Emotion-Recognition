# Glossary

One name per concept. Binding on code, identifiers, comments, documentation, and
user-facing output.

Terms are derived from `pgvector-db/schema.sql`, which is the authority: the
database is the contract every sub-project shares, so where a table or column
already names a concept, that name wins.

Row counts are from the development corpus on 2026-08-22 and are illustrative.

---

## Core entities

### video

One video file and its annotations. Table `videos`, keyed by `video_id`, unique
by `filename`. The unit everything else is scoped to.

Say "video". Not "clip", "recording", or "file" — "file" means the file on disk
in the video store.

### person

One person **as detected within a single video**. Table `persons`, keyed by the
pair `(video_id, person_id)`.

`person_id` comes from the CAS and is unique only *within* its video, so a
person is never identified by `person_id` alone. Always write the pair, and
always say "a person in a video" where scope could be misread.

### global person

One real individual, linked across videos. Table `global_persons`, referenced by
`persons.global_person_id`.

**Use "global person", not "global identity" or "cross-video person."** The
schema says `global_persons` / `global_person_id` / `global_person_match_score`
throughout, and the entity should not have a second name in prose.

> **Naming tension, deliberate:** the sub-project is called
> `global-identity-linker` and its package is `identity`. Those names are fixed.
> Resolve it this way — the **process** is *identity linking*, the **thing
> produced** is a *global person*. The linker assigns global persons. Do not use
> "identity" as a noun for the entity.

### model

An upstream annotation model — name, version, source. Table `models`. Referenced
by embeddings; identifies what produced a given annotation.

---

## Time and structure

### segment

A span of a video. Table `segments`. **The umbrella term**, distinguished by
`kind`:

| `kind` | Meaning | Corpus |
| --- | --- | --- |
| `sentence` | One transcript sentence | 725 |
| `shot` | One camera shot | 195 |

Say "segment" when the kind does not matter, and **"sentence segment" or "shot
segment" when it does**. Do not use bare "sentence" for a segment — the code
currently does this in places and it hides the distinction.

### token

One word of the transcript, with its part-of-speech tag and named-entity label.
Table `linguistic_tokens`, belonging to a segment.

Say "token". "Word" refers to the `word` column specifically.

### presence

A span during which a person is present in one modality. Table `presences`.

| `modality` | Meaning | Corpus |
| --- | --- | --- |
| `visible` | On screen | 529 |
| `speech` | Speaking | 186 |

A presence is a *span*; a detection is a *frame*.

### detection

One bounding box for one person at one frame. Tables `face_detections` and
`person_detections` — face box and body box respectively.

Say "face detection" or "person detection" when the distinction matters,
"detection" otherwise. Detections belong to a presence.

---

## Emotions

### base emotion

One emotion reading: a person, a modality, a granularity, a time span, plus
valence/arousal/dominance and a dominant label. Table `base_emotions`.

| `modality` | `granularity` | Corpus |
| --- | --- | --- |
| `video` | `frame` | 42,930 |
| `text` | `sentence` | 1,450 |
| `audio` | `sentence` | 725 |

**"Base" is meaningful and the name stays.** The upstream models do not share an
emotion inventory — some emit far more granular emotions than others — so those
inventories are reduced to a common base set, which is what makes video, text,
and audio output comparable at all. That reduction happens **outside this
project**, during CAS creation; this project only stores and displays the
result. Documentation here should say that much and link no further: the
definition belongs to the pipeline that produces it, not to us.

Say "base emotion" for the row, matching the table.

### emotion score

One `(label, score)` pair belonging to a base emotion. Table `emotion_scores` —
375,205 rows, since each base emotion carries a score for every label in its
model's inventory.

A base emotion has one `dominant_label`; the scores are the full distribution.

Note that **label vocabularies are model-native and differ by modality**: video
uses eight capitalized labels (`Anger`, `Happiness`, …), text uses lowercase
GoEmotions-style labels (`joy`, `approval`, `curiosity`, …), and audio uses its
own set (`happy`, `angry`, `fearful`, …). `dominant_label` also carries `<unk>`
and empty values in the current corpus. Do not assume a shared label set when
querying across modalities — the comparable axis is valence/arousal/dominance.

### modality

Which channel an annotation came from: `audio`, `video`, or `text` for emotions;
`visible` or `speech` for presences.

Always one of those literal values. Do not write "the visual modality" for
`video`.

### embedding

A vector identifying a person by face (512-d, `face_embeddings`) or voice
(192-d, `voice_embeddings`). What identity linking compares.

---

## Jobs

### job

A kind of work that runs against the corpus. Two exist: **the importer**
(`cas-to-postgres-importer`) and **the identity linker**
(`global-identity-linker`). The `job_runs.job` column holds the kind.

### job run

One execution of a job. Table `job_runs`, one row per execution, with status,
phase, progress, and a heartbeat.

**Say "job run" for the row or the execution.** Bare "run" is ambiguous — it is
also a verb and the name of several functions — so use it only as a verb.
Do not write "import job" for a run of the importer; that is "an importer run".

### heartbeat

A periodic `heartbeat_at` write proving the process behind a `running` row is
alive. A run whose heartbeat has gone stale is presumed dead.

---

## Pipeline and storage

### CAS

A UIMA Common Analysis Structure — the `.xmi` file the upstream DUUI pipeline
produces, holding a video's annotations. Always uppercase.

Say "a CAS" and "CAS file", never "a cas" or "the XMI" (the `.xmi` is the file
format the CAS is serialized in).

### sofa / view

UIMA terms for the subjects of analysis inside a CAS. Used only where the code
genuinely touches UIMA structure. Do not use them for project-level concepts.

### typesystem

The UIMA type descriptors needed to read a CAS, shipped in
`cas-to-postgres-importer/src/resources/typesystems/`. One word, not "type
system", matching the filenames.

### video store

The shared directory holding video files, where the importer writes and the
webapp reads. Configured by `DUUI_VIDEO_DIR`; a video's file is
`<video store>/<videos.filename>`.

Say "video store". Not "media directory" or "video folder".

---

## Project vocabulary

### DUUI

Docker Unified UIMA Interface — the upstream pipeline framework. Retained as the
prefix for environment variables (`DUUI_*`), image names, and log prefixes.

### the corpus

All videos currently in the database. Used for operations that span everything —
identity linking is corpus-wide.

### Bundestag

The **source material**, not the project. Correct in "the Bundestag corpus" or
"Bundestag proceedings"; incorrect as part of any project, image, service,
volume, or directory name — those are all `video-emotion-visualization`.

---

## Sub-project names

Fixed and not to be changed. Refer to each by its exact directory name:

| Directory | Package | What it is |
| --- | --- | --- |
| `webapp` | `backend` | The webapp: FastAPI backend plus static frontend |
| `cas-to-postgres-importer` | `importer` | The importer: CAS files into the database |
| `global-identity-linker` | `identity` | The identity linker: assigns global persons |
| `pgvector-db` | — | Postgres 16 + pgvector, with the schema baked in |

In prose, "the importer", "the linker", "the webapp", and "the database" are the
short forms.

> **"Viewer" is retired.** The current code and docs use it 92 times against 74
> for "webapp", for the same thing. **Use "the webapp" everywhere** — it matches
> the directory name, which is fixed and is what a reader actually sees. Not
> permitted as a soft alias: a permitted alias is how the count reached 92–74.
