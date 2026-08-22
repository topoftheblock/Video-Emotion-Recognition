# Phase 2 — Fact ledger

*Detailed plan for Phase 2. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` in progress, started 2026-08-22.
Branch: `code-cleanup/phase-2`.

## 2.0 What this phase is for

To establish **what the system actually does**, verified against code, so that
Phases 5 and 7 have something to write from other than the existing comments —
which [§5 of the plan](README.md#5-cross-cutting-rules) forbids relying on.

Two outputs:

- **Verified facts**, per module — [`phase-2-modules.md`](phase-2-modules.md)
- **A discrepancy register** — §2.3 below, feeding Phases 3, 5, 6 and 7

Nothing is fixed in this phase. Discrepancies are recorded, not corrected. Code
*bugs*, as opposed to documentation errors, follow the stop-and-ask rule in §5.

## 2.1 Method

For each sub-project, in the Phase 5 order (smallest first): `pgvector-db` →
`global-identity-linker` → `cas-to-postgres-importer` → `webapp`.

Per module: what it owns, what it exports, what it depends on, and any behavior
that is not obvious from the signature. **Read the code; never the comments.**
Where a claim can be checked against the running database or the test suite,
check it rather than reasoning about it.

Anything that cannot be verified is recorded as unverified, with what would be
needed to settle it. It is not guessed at.

## 2.2 A correction carried over from Phase 1

Phase 1 recorded, as evidence that `pgvector-db/data_schema_with_types.md` was
stale, that `job_runs` is missing from it. **That was wrong**, and it is
corrected here and in the three places it was propagated to.

`data_schema_with_types.md` is not a description of the running database. It is
the **design document** mapping the UIMA CAS type system onto tables, and it says
so in its own header. `job_runs` is an operational table that no CAS produces, so
its absence from a pipeline-export design is correct rather than stale.

The mistake is instructive, and is exactly the failure the phase ordering exists
to catch: a plausible inference — file names two things, one is missing,
therefore stale — made without reading the document. Phase 1 should have read it.
Phase 2 did.

## 2.3 Discrepancy register

Verified findings. Every entry names where it is resolved.

### D1 — the design specifies emotion fusion that does not exist
**Phase 7 (docs), possibly Phase 3.** `data_schema_with_types.md` specifies
`FusedEmotion` (`fused_id`, `fusion_method`, `target_modality`, …) and
`EmotionFusionReference` (`fused_id`, `source_emotion_id`) as an n:m bridge for
combining emotions across modalities. **Neither has a table in `schema.sql`, and
nothing in the importer writes one** — `grep -i fus` over the schema returns
nothing.

The document's header carefully lists four known divergences; this is not among
them. Either the fusion layer was planned and never built, or it was dropped and
the spec was not updated. Needs a decision: implement, or record as unbuilt.

### D2 — the design document is written in mixed German and English
**Phase 7.** Headings and many column descriptions are German
("Metadaten & Video Layer", "Fortlaufender Index des Segments", `'shot'` oder
`'sentence'`), the rest English. Phase 1 settled on US English throughout.

### D3 — `data_schema_with_types.md`'s stated divergences are accurate
**No action.** Recorded because it is evidence, not a problem. Checked against
`schema.sql`: `begin`/`end` → `begin_offset`/`end_offset` (reserved word);
`Detection` split into `face_detections` and `person_detections`; `segments` also
fed by `SpeakerSentence` for `kind = 'sentence'`; text emotion from a second UIMA
type. All four hold.

Its composite-key note is *directionally* right and wrong in detail — the keys
really are `(video_id, <id>)`, but the ids do not "restart at 1" per document.
See D7.

### D4 — no `connect_timeout` in any application code
**Phase 2 → Phase 5 or a bug fix.** Carried from
[Phase 0 §0.2](phase-0-baseline.md). `webapp/src/backend/db.py`,
`identity/db.py` and the importer all call `psycopg2.connect()` with no timeout.
Against a host that blackholes packets, `create_app()` hangs at startup with no
diagnostic. Compose masks it; a wrong or firewalled database IP triggers it.

### D5 — the importer announces work it then skips
**Phase 5.** Carried from Phase 0 §0.5. `pipeline.py:207` prints
`Loading CAS data from <file>...` before the already-imported check at `:227`;
the actual load is at `:253`.

### D6 — emotion labels are model-native and differ by modality
**No action; already in the glossary.** Carried from Phase 1. Video uses eight
capitalized labels, text lowercase GoEmotions-style ones, audio its own set, plus
`<unk>` and empty `dominant_label` values.

### D7 — a rationale comment's illustration is contradicted by the data
**Phase 5.** `linking.py`'s header explains the composite `(video_id, person_id)`
key by asserting that "two videos routinely both have a 'person 1'."

**The underlying reason is correct; the illustration is false.** `person_id` is
the CAS's `xmi:id`, which is a *document-wide* counter across all annotations,
not a small per-type counter. In the corpus the values are large and sparse —
`32608`, `70438`, `87720`, `132525`, `1755` — and **no `person_id` occurs in more
than one video**. The ranges differ wildly per file, which is itself the real
evidence that these are document-scoped ids and cannot be assumed unique
corpus-wide.

So the composite key is right, and the justification should be the verifiable
one (per-document counters, ranges that differ per file, collisions therefore
possible) rather than a collision that does not occur in this data. A textbook
case of the guide's §2: the comment sounds authoritative and is wrong in its
particulars.

### D8 — `--on-existing replace` does not preserve `video_id`
**Phase 5 (document), Phase 7 (operations).** Verified by observation during
Phase 0: `first2.mp4` was `video_id 1` before an `--on-existing replace` run and
is `video_id 47` after it. Replace deletes the row and inserts a new one, so the
`BIGSERIAL` advances.

Consequences worth documenting: any external reference to a `video_id` — a
bookmarked webapp URL, a saved query, an exported result — breaks after a
replace. The gap from 10 to 47 also shows the sequence has been consumed by
earlier rolled-back imports, so ids are neither stable nor contiguous.

Not a bug: delete-and-insert behaving as delete-and-insert. But it is undocumented
and it is the kind of thing a user discovers the hard way.

### D9 — `/api/stats` is served and tested but has no consumer
**Phase 3 (keep or remove), Phase 6 (tests).** `routes/stats.py`,
`queries/stats.py` (120 lines, four functions) and the `/api/stats/{video_id}`
endpoint are live and return 200. **Nothing calls them.** `grep` over the whole
frontend finds one hit, and it is the comment in `api.js` saying so.

The comment is accurate — one of the few that checks out: the emotion panels
replaced the insights panel that used to read it. `test_routes.py` asserts the
route exists, and `test_emotion_series.py` / `test_video_scoping.py` exercise the
query functions, so it is tested code with no product behind it.

Decision needed: remove the route and its queries, or keep them as a documented
API for external use. Not a bug either way.

<!-- New entries append here as each sub-project is read. -->

## 2.4 Shared contracts

Verified from both sides. These are what `docs/architecture.md` will own, and
what no sub-project README may restate.

### The database

The only integration point between the four parts. There is no API between
sub-projects, no message queue, and no shared code — everything one part tells
another, it says by writing a row.

| Writer | Reader | Through |
| --- | --- | --- |
| importer | webapp | every CAS-derived table |
| importer | linker | `face_embeddings`, `voice_embeddings`, `persons` |
| linker | webapp | `global_persons`, `persons.global_person_id`, `persons.global_person_match_score` |
| importer, linker | webapp | `job_runs` |

`persons.global_person_id` is written **only** by the linker — verified: no
typesystem defines `GlobalPerson` and no parser step touches the column.

### The video store

One directory, `DUUI_VIDEO_DIR`. The importer copies each CAS's video in under
the exact name it writes to `videos.filename`; the webapp mounts the same
directory read-only at `/media` and resolves a video as
`<video store>/<videos.filename>`. **Filename is the join key, not `video_id`** —
which is what makes D8 survivable.

### Environment variables

Every sub-project defines its own config module reading the same `DUUI_*`
names. No config code is shared. Compose passes identical values to every
service, which is what keeps both ends of the database and video-store contracts
pointing at the same place.

The two the contracts depend on are `DUUI_DB_*` and `DUUI_VIDEO_DIR`.

### `job_runs`

The channel from the two batch jobs to the webapp. Declared identically in four
places. A writer opens its **own autocommit connection**, separate from the
transaction doing the work, so progress stays visible while a long import or
recompute sits uncommitted. The webapp polls `GET /api/jobs` and treats a run
whose heartbeat is older than `STALE_AFTER_SECONDS = 30` as dead.

## 2.5 Progress

| Sub-project | Modules | Read |
| --- | --- | --- |
| `pgvector-db` | 2 files | `[x]` both verified |
| `global-identity-linker` | 5 modules | `[x]` all read, claims checked |
| `cas-to-postgres-importer` | 15 modules | `[~]` structure and contracts verified; `config.py`, `media.py` and the 11 parsers not yet read line by line |
| `webapp` | 14 backend, 15 JS, 12 CSS | `[~]` backend structure and the live API surface verified; `query_agent/`, the JS modules and the CSS not yet read line by line |

**What "read" means here.** Every module has been placed: what it owns, what it
exports, what depends on it, and the contracts it participates in. Specific
checkable claims were checked against the database, the typesystems, or the
running app. What remains is line-by-line reading of the four largest areas,
which is where Phase 5 will spend its time anyway — the question is whether that
reading happens now or as part of rewriting each file.

## 2.6 Exit criteria

- [x] Every module placed and recorded in [`phase-2-modules.md`](phase-2-modules.md)
- [x] Shared contracts written up (§2.4)
- [x] `data_schema_with_types.md` verified against `schema.sql` — D1–D3
- [x] Discrepancy register: D1–D9, every entry assigned to a phase
- [ ] Line-by-line reading of `config.py`, `media.py`, `parsers/`, `query_agent/`, the frontend JS and CSS — see §2.5
- [ ] README claims about commands and paths verified — 968 lines, not yet started
