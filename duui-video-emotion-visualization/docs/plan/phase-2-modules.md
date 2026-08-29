# Phase 2 — Verified module facts

*Working material for [Phase 2](phase-2-ledger.md). Everything here was read
from the code and, where checkable, verified against the running database or the
test suite. Existing comments were **not** treated as a source; where one made a
checkable claim it was checked, and the result is in the
[discrepancy register](phase-2-ledger.md#23-discrepancy-register).*

Order follows Phase 5: smallest sub-project first.

---

## pgvector-db

Two files. No `src/`, no tests — a database image, by decision.

### `schema.sql` — 307 lines

Creates 14 tables and their indexes; baked into the image as
`/docker-entrypoint-initdb.d/01-schema.sql`.

**Runs only on an empty data directory.** Postgres's entrypoint executes
`initdb.d` scripts on first start of a fresh volume and ignores them thereafter,
so an existing volume never picks up schema changes. Verified in Phase 0: a
`down`/`build`/`up` cycle left the data intact and did not re-run the script.

Tables, grouped as the schema groups them:

| Group | Tables |
| --- | --- |
| Metadata | `videos`, `models` |
| Identity | `global_persons`, `persons` |
| Structure | `segments`, `linguistic_tokens` |
| Biometrics | `face_embeddings` (512-d), `voice_embeddings` (192-d) |
| Presence | `presences`, `face_detections`, `person_detections` |
| Emotion | `base_emotions`, `emotion_scores` |
| Operational | `job_runs` |

Verified properties:

- **Composite keys throughout.** Everything CAS-derived is keyed
  `(video_id, <xmi id>)`, and foreign keys between them are two columns. See D7
  for why — and for what the existing comment gets wrong about it.
- **`videos.video_id` is a `BIGSERIAL`, not stable.** `--on-existing replace`
  deletes and re-inserts, taking a new id. Observed: `first2.mp4` moved from 1
  to 47. See D8.
- **`job_runs` is declared in four places** — here plus each of the three Python
  services — as `CREATE TABLE IF NOT EXISTS`. All four are byte-identical
  (checked). It carries `WITH (fillfactor = 70)`, consistent with a table whose
  rows are updated repeatedly by heartbeats.
- `emotion_scores` is the only table with a plain surrogate key (`score_id`).

### `data_schema_with_types.md` — 286 lines

**The design document, not a description of the database.** Maps the UIMA CAS
type system onto tables. Broadly accurate; states four of its own divergences,
all of which check out (D3). Two problems: it is written in mixed German and
English (D2), and it specifies a fusion layer that does not exist (D1).

---

## global-identity-linker

Package `identity`. Five modules. Its entire input and output is the database:
it opens no files and reads no CAS.

### `__main__.py` — 104 lines

Entry point; `python -m identity`. Takes no arguments — the corpus is the input.

Verified control flow: opens a `JobRun`, connects, calls
`recompute_global_persons(cursor, progress=…)`, commits, and prints a summary.
On any exception it rolls back, re-raises, and the `__main__` guard prints
`[duui_global_identity] ERROR: …` and exits 1.

**The wipe and the rebuild share one transaction.** A failure mid-run rolls back
to the identities that existed before it started, never to a cleared corpus.
Confirmed by reading: a single `conn`, one `commit()` after the recompute.

`_progress` prints one line per 100 persons and on the last. Observed live:
`...23/23 persons processed`.

### `linking.py` — 333 lines

The matching logic. Public: `clear_global_persons`, `build_centroids`,
`link_person`, `recompute_global_persons`. Private helpers for the match
query, id minting, and score writing.

How it actually works, verified against the SQL:

1. Averages each person's embeddings into one **centroid** per person per
   modality (`avg()` over pgvector's vector type), materialized into a
   `TEMP TABLE` once per run.
2. For each person, finds the nearest centroid **in a different video**
   (`c2.video_id != c1.video_id`) by cosine distance (`<=>`), takes the single
   best under threshold, and either joins that person's existing global person
   or mints a new one.
3. **Face first, voice as fallback** — `_MODALITIES` is ordered, so a person with
   no usable face embedding can still link by voiceprint.
4. Writes `persons.global_person_match_score` for every person, linked or not.

Verified claims from its header comment:

- *"the type isn't even present in the shipped typesystems"* — **confirmed.** No
  file in `cas-to-postgres-importer/src/resources/typesystems/` mentions
  `GlobalPerson`. Nothing in the importer populates `global_person_id`; this job
  is the only writer.
- *"two videos routinely both have a 'person 1'"* — **false for this corpus.**
  See D7.
- Temp tables are schema-qualified `pg_temp.*` throughout — confirmed in
  `_MODALITIES`.

Observed behavior on the live corpus: 23 persons → 21 linked into 8 global
persons.

### `config.py` — 51 lines

**Already rewritten to the style guide in Phase 1** as the trial file. Owns
`DB_CONFIG` and the two distance thresholds (face 0.30, voice 0.35, both
overridable). No derivation for either threshold exists in the repository.

### `db.py` — 14 lines

**Already rewritten in Phase 1.** One function, `get_db_connection()`. No
`connect_timeout` — D4.

### `job_runs.py` — 258 lines

The `JobRun` context manager. Near-identical to the importer's copy: 35 diff
lines out of 258, almost all comment text, plus one log prefix
(`[duui_global_identity]` vs `[duui_parser]`). Duplication is deliberate (§1 of
the plan); the divergent prose is a Phase 5 task.

Verified behavior:

- Opens its **own autocommit connection**, separate from the job's transaction,
  so heartbeats stay visible while the recompute sits uncommitted.
- A daemon thread writes a bare heartbeat every 5s; call-site updates are
  throttled to 1/s but a **phase change always forces a write**.
- On `start()`, marks any still-`running` row for the same job as `failed` —
  a killed job never writes its own final row, so the next run cleans up.
- Every database failure is swallowed and disables status reporting rather than
  breaking the job.

---

## cas-to-postgres-importer

Package `main`. 15 modules plus `resources/`. Reads CAS `.xmi` files, writes the
database, and copies each CAS's video into the video store.

### `__main__.py` — 82 lines

Entry point; `python -m main [paths...] [--on-existing skip|replace]`. One
helper, `_split_args`, separates flags from paths. No path arguments means
`default_input_paths()`.

### `pipeline.py` — 373 lines

Orchestration. Public: `parse_and_insert`, `default_input_paths`,
`resolve_xmi_paths`, `describe_missing_inputs`, `run`, `run_many`.

`run_many` is what `__main__` calls; it loads and patches the typesystem **once
per batch** rather than per file. `run` handles a single CAS.

Verified order of operations in `run`, which matters for D5:

1. `:207` prints `Loading CAS data from <file>...`
2. `:220` `read_video_filename(tree)` — parses the raw XML with lxml
3. `:227` the already-imported check, which may skip
4. `:253` `load_cas_from_xmi(...)` — the actual expensive CAS load

So the skip path genuinely avoids the CAS parse, but **still parses the XML
tree**, and the "Loading" message prints before either. See D5.

`parse_and_insert` runs every step in `PARSE_STEPS` inside one transaction,
threading a `context` dict so later steps can read
`context["global_video_id"]`.

### `parsers/` — 11 modules, one per annotation layer

`__init__.py` defines `PARSE_STEPS`, whose **order is a hard dependency chain**,
documented inline and verified against what each step reads:

| # | Step | Depends on |
| --- | --- | --- |
| 1 | `video` | — resolves `context["global_video_id"]`, so it must be first |
| 2 | `model` | |
| 3 | `person` | builds the face/voice → person maps |
| 4–9 | `segment`, `token`, `embedding`, `presence`, `detection`, `emotion` | all carry `person_id` foreign keys, so all follow `person` |
| 10 | `text_emotion` | GoEmotions-style text emotion, a **second** UIMA type not in the design doc |

### `typesystem.py` — 292 lines

Loads and merges the three shipped typesystem descriptors, and **synthesizes stub
type definitions** for types the XMI references but no descriptor defines
(`_find_undefined_referenced_types`, `_stub_type_xml`). Without this a real CAS
fails to load.

`loading_cas_quietly()` suppresses cassis's `Type with name [X] not found!`
warning for exactly the types in `IGNORED_ABSENT_TYPES`, matched literally per
name so nothing else is swallowed. Overridable via `DUUI_TS_*`.

### `media.py` — 363 lines

The video half. Finds media sofas in the raw XML, reads the video filename,
selects the video sofa, strips media sofas before the CAS parse, and either
copies the companion video from the input directory or **extracts it from the CAS
itself** when no file exists. `SofaPayload` carries the embedded data.

### `config.py` — 341 lines

Every path, credential, and UIMA type name. 146 of its 341 lines are comment —
the densest file in the project, and a major Phase 5 target.

### `db.py`, `cas_views.py`, `identity_resolution.py`, `job_runs.py`

- `db.py` (51) — connection plus `find_video_by_filename` and `delete_video`,
  the two the skip/replace decision needs.
- `cas_views.py` (76) — `select_across_views` and `select_exact_type`; a CAS
  keeps annotations in several views and a plain `select` misses them.
- `identity_resolution.py` (85) — parses person labels and resolves a face or
  voice identity feature structure to a `person_id`.
- `job_runs.py` (257) — the importer's copy of `JobRun`. See the linker's entry.

---

## webapp

Package `backend`, plus a `frontend/` served as static files. **No build step** —
`index.html` loads `js/main.js` as an ES module and FastAPI serves the files
unchanged.

### Backend — 14 modules

`app.py` exposes `create_app()` as a factory, so importing the package has no
side effects. It creates `VIDEO_DIR`, calls `jobs_query.ensure_table()`
best-effort, registers five routers, then mounts `/media` and `/` **last**
because `/` is a catch-all.

`NoCacheStaticFiles` adds `Cache-Control: no-cache` to every static response —
the frontend is unversioned, so a rebuilt page could otherwise load new HTML
against cached JS.

**The API surface, verified live against the running app:**

| Endpoint | Status | Notes |
| --- | --- | --- |
| `GET /healthz` | 200 | Runs a real `SELECT 1`; 503 if the database is unreachable |
| `GET /api/videos` | 200 | |
| `GET /api/videos/{id}/data` | 200 | The one big per-video payload the frontend renders from |
| `GET /api/persons/global` | 200 | |
| `GET /api/jobs` | 200 | `{"jobs": [], "stale_after_seconds": 30}`; empty list, never 404 |
| `GET /api/stats/{id}` | 200 | **Served, tested, and called by nothing.** See D9 |
| `POST /api/ask` | — | Natural-language → SQL |

`queries/` holds the SQL: `videos.py` (184) is the largest and assembles the
per-video payload; `stats.py` (120) has no consumer; `persons.py` (53);
`jobs.py` (93) owns `STALE_AFTER_SECONDS = 30` and the fourth copy of the
`job_runs` DDL.

`query_agent/` is the Ask panel: `agent.py` (248) drives the LLM loop,
`schema_context.py` (355) supplies the schema description, `sql_guard.py` (95)
validates that generated SQL is a single read-only `SELECT` and runs it in a
`READ ONLY` session.

### Frontend — 15 JS modules, 12 stylesheets

`main.js` is the only module with no exports — it is the entry point.
`state.js` holds the single shared mutable object and the Okabe-Ito palette.
`api.js` centralizes fetch and error policy. `panels/` holds the five sidebar
panels. `overlay.js`, `player.js`, `subtitles.js`, `videoLoader.js` drive
playback and the canvas overlay.

CSS is split by region — `tokens.css` for custom properties, then `base`,
`layout`, `topbar`, `sidebar`, `stage`, `emotions`, `ask`, `jobs`,
`responsive`, `adaptive`, with `main.css` importing them.
