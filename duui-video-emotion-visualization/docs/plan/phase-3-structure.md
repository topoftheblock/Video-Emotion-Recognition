# Phase 3 — Structure: naming, splitting, merging

*Detailed plan for Phase 3. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` plan approved 2026-08-22; one open question in §3.9.
Branch: `code-cleanup/phase-3`.

## 3.0 What this phase is for

All path-changing churn, in one place, before anything is written about those
paths. **No behavior changes.** Every step is a rename, a move, or a split; the
suite must sit at 150/150 after each.

It **was** the highest-risk phase. It is not any more: the data is rebuilt from
its source CAS files rather than migrated (§3.1), so there is nothing to lose.

---

## 3.1 The rename hazard — read before touching `docker-compose.yml`

There are **two** name-shaped things that look like the stale project name and
are not the same problem.

### (a) The Compose project name — destructive

`docker-compose.yml:38` reads `name: duui-bundestag-stack`. Compose derives
named-volume names from it, which is why the volumes are
`duui-bundestag-stack_db_data` and `duui-bundestag-stack_video_media`.

**Changing that line points Compose at new, empty volumes.** The database and
the video store are not deleted — they are orphaned, which looks identical to
data loss from the user's side.

### (b) The database name — a separate change, also destructive

`duui_bundestag` appears as the `DUUI_DB_NAME` default in six places. It is the
name of a database **that exists inside the volume**, so changing the default
points the services at a database that is not there.

**Decided 2026-08-22: rename it.** New name pending — see §3.9.

### Both hazards are dissolved by rebuilding from source data

**Decided 2026-08-22: no migration.** The volumes are destroyed and the corpus is
re-imported from the CAS files, which is possible because the source data still
exists. That removes the risk from both renames at once — there is nothing to
orphan — and turns the riskiest step in the plan into the **most thorough test
in it**: a full rebuild that exercises the renamed package, the renamed database,
the split modules, and all four sub-projects end to end.

The recreation is specified in §3.7.1, run as step 10.

> A migration procedure is still owed to *users*, who may rename with data they
> cannot reproduce. It is written into `docs/operations.md` during Phase 7 — the
> stub already has the heading — but **not executed here**.

> Confirmed in Phase 0: renaming a **service** (`db` → `pgvector-db`) is
> data-safe. Only the **project** name moves volumes.

---

## 3.2 The stale name purge — verified, file by file

33 occurrences. Read individually, they fall into three groups.

### Group A — the dead project name. Remove (10 occurrences)

| Where | What |
| --- | --- |
| `docker-compose.yml:38` | `name: duui-bundestag-stack` → `duui-video-emotion-visualization`. **§3.1(a) applies.** |
| `webapp/src/backend/app.py:63` | `FastAPI(title="DUUI Bundestag Video Viewer")` — **user-facing**, and carries the retired word "Viewer" too. → **`"DUUI Video Emotion Visualization"`** (decided 2026-08-22) |
| `webapp/src/backend/app.py:2` | Module docstring, "DUUI Bundestag pipeline" |
| `webapp/docs/a11y-ci.yml` | 6 × `duui-bundestag-stack/` in `paths:` filters and `working-directory:`. Repoint at `duui-video-emotion-visualization/`. **Still not activated** (Phase 7 also fixes its false "no CI" premise). |

### Group B — the database name. Rename (7 occurrences)

`.env.example:60`, `docker-compose.yml` × 5 (the `DUUI_DB_NAME` default, plus
`POSTGRES_DB` and the healthcheck's `pg_isready -d`), and `schema_context.py:15`.

Also **`.env`**, which is untracked but currently sets
`DUUI_DB_NAME=duui_bundestag` on this machine — set in Phase 0 so host-side tests
could reach the database. It must change with the rest or every DB-backed test
silently skips again.

### Where the "viewer" → "webapp" purge belongs

Decided during step 1, because `app.py` carried both problems in one line.

- **Phase 3** owns identifiers, filenames, and **user-facing strings** — anything
  a person or another program consumes. The FastAPI `title=` is user-facing (it
  is the browser tab and the OpenAPI document), so it was fixed here.
- **Phase 5** owns prose in comments and docstrings. All 92 remaining "viewer"
  occurrences are prose, and Phase 5 rewrites those comments wholesale — fixing
  them now would mean editing the same lines twice.

Checked before drawing the line: **no identifier anywhere contains "viewer"** —
no variable, function, class, CSS class, or custom property. It is purely a
prose problem, which is what makes the split clean.

### Group C — genuine references to the corpus. Keep (17 occurrences)

`linking.py`, `media.py`, `text_emotion.py`, `typesystem.py`, `config.py` × 2,
`cas_views.py` × 2, `embedding.py`, `identity_resolution.py`, `emotion.py` × 3,
`token.py`, `schema_context.py:25`, and two tests.

Every one describes the actual source material — "the real Bundestag CAS", "the
Bundestag corpus". Correct per the glossary. **A global find-and-replace would
have destroyed all seventeen**, which is why the plan required reading each file.

*(Counted as 16 when this plan was written; the recount after the splits found
17. The original count used a narrower file filter and predated `config.py`
becoming `cas/types.py`.)*

Also out of scope: the sibling directory `duui_bundestag_pipeline/` and the root
`.github/workflows/ci.yml` that targets it. Different project.

---

## 3.3 Package name: `main` → `importer`

**Decided 2026-08-22: rename.**

`main` is not a name — it says nothing about what the package does, while its two
siblings (`backend`, `identity`) do. It also collides conceptually with the
`__main__.py` inside it, so `main/__main__.py` reads as a stutter.

The one hard constraint from the root `pyproject.toml` — that the three package
names stay mutually distinct, since all three `src/` roots share one
`pythonpath` — is satisfied: `importer`, `backend`, `identity`.

What it touches:

- `cas-to-postgres-importer/src/main/` → `src/importer/` (`git mv`)
- Every `from main.… import` / `import main` in `src/` and `tests/`
- `Dockerfile`: `ENTRYPOINT ["python", "-m", "main"]` → `-m importer`
- Root `pyproject.toml` needs **no** change — it lists the `src` root, not the package
- Log prefix `[duui_parser]` is a separate question (§3.6)

**Checked:** no installed distribution provides a top-level `importer`,
`backend`, `identity` or `main` module, so nothing shadows and nothing is
shadowed.

---

## 3.4 Splitting oversized modules — measured, not guessed

| Module | Lines | Finding | Recommendation |
| --- | --- | --- | --- |
| `importer/config.py` | 341 | **Two unrelated things.** Lines 1–124 are deployment settings read from `DUUI_*`; lines 125–341 are UIMA type names, injected fallback XML and ignored-type sets — domain constants that never vary per deployment. | **Split.** `config.py` (settings) + `uima_types.py` (vocabulary). The clearest split in the project. |
| `importer/media.py` | 363 | Two concerns: raw-XML sofa manipulation (`find_media_sofas`, `select_video_sofa`, `strip_media_sofas`, `SofaPayload`) and video file placement (`place_video_file`, `ensure_video_available`). | **Split**, second priority. |
| `importer/pipeline.py` | 373 | Orchestration (`run`, `run_many`, `parse_and_insert`) plus input-path resolution (`default_input_paths`, `resolve_xmi_paths`, `describe_missing_inputs`). | **Split** → `inputs.py` (confirmed). |
| `query_agent/schema_context.py` | 355 | **Not a module — a data blob.** One string constant spanning lines 23–355. "355 lines" overstates its complexity. | **Do not split.** But see §3.5. |
| `identity/linking.py` | 333 | Cohesive: every function serves cross-video matching. | **Leave.** |
| `js/panels/emotions.js` | 359 | 14 functions; rendering plus statistics (`meanScores`, `meanDimension`, `dominantOf`, `orderLabels`). | **Split** the math helpers out (confirmed). |
| `css/sidebar.css` | 391 | **Under-sectioned, not over-long** — two section banners in 391 lines. | **Add sections first**, split only if still unwieldy. |

## 3.4b Grouping files into packages

Decided 2026-08-22, from the import graphs rather than from filenames.

### `importer/cas/` — the strongest case in the project

**All 11 parsers import the same four modules and nothing else structural:**
`cas_views`, `config`, `typesystem`, `identity_resolution`. That identical
pattern, repeated 11 times, is a real boundary: those modules are the toolkit for
*reading a CAS*, and everything else in the package is orchestration, storage, or
file I/O.

```
importer/
  __main__.py  config.py  db.py  job_runs.py
  pipeline.py  inputs.py  video_files.py
  cas/       views.py  typesystem.py  types.py  sofas.py  person_resolution.py
  parsers/   (11 modules)
```

Without it the planned splits leave **12 flat modules** beside `parsers/`; with
it, seven and two packages. It also removes the `cas_views.py` stutter —
`cas/views.py` — and gives `uima_types.py` a home as `cas/types.py`.

Members: `views.py` (was `cas_views.py`), `typesystem.py`, `types.py` (the UIMA
vocabulary split out of `config.py`), `sofas.py` (the raw-XML half of
`media.py`), `person_resolution.py`.

### `js/lib/` and `js/playback/`

From the frontend import graph:

- **`lib/`** — `api.js`, `dom.js`, `format.js`. The only three modules with
  **zero internal imports**; generic primitives holding no application state.
  That property is the evidence. Named `lib` rather than `helpers` to follow the
  convention readers already know from other JavaScript projects — the one place
  in this project where a familiar abbreviation beats a plainer word.
- **`playback/`** — `player.js`, `subtitles.js`, `overlay.js`. All three import
  `dom` + `state` and nothing else structural, and all three render synchronized
  to playback time. `videoLoader.js` looks similar but is not: it orchestrates
  loading and reaches into three panels, so it stays top level.

```
js/
  main.js  state.js  videoLoader.js  legend.js
  lib/       api.js  dom.js  format.js
  playback/  player.js  subtitles.js  overlay.js
  panels/    (5 modules)
```

Cost, and it is real if small: with no build step every import path is literal,
so `"./api.js"` becomes `"../lib/api.js"` in every consumer.

`legend.js` stays top level. It is a 27-line sidebar disclosure that is arguably
a panel; forcing it into one of the groups would be tidier than it is true.

### Not grouped, deliberately

- **CSS.** `main.css` imports the 11 stylesheets in **cascade order** and says so:
  tokens first because 10 of the other 11 read its custom properties, `responsive`
  and `adaptive` last because their overrides must win. The organizing principle
  is *sequence*, not category, and folders would imply an independence that does
  not exist. The flat ordered list in `main.css` is the honest structure.
- **`webapp/src/backend/`.** Already three top-level modules plus `routes/`,
  `queries/`, `query_agent/`. Correct as it stands.
- **`identity/`.** Five flat modules. Too small; folders would be overhead.
- **`webapp/tests/`.** A `tests/support/` grouping is wanted, but it belongs to
  Phase 6, which already specifies it.

## 3.5 A third description of the schema

`schema_context.py` describes the database to the LLM. `schema.sql` defines it.
`docs/database.md` will document it. **Three descriptions, one of which is prose
inside a string literal.**

Nothing keeps them in step, and a drifted `SCHEMA_CONTEXT` makes the Ask panel
generate SQL against a schema that no longer exists.

Not a Phase 3 split, but it needs an owner. Options: generate it from
`schema.sql`; add a test that fails when they diverge; or accept the risk and
document it. **Recommend the test** — cheapest, and Phase 6 is already going to
be there.

## 3.6 Smaller questions, with answers

- **Thin route modules** — `routes/persons.py` (13), `routes/stats.py` (14),
  `routes/jobs.py` (23). **Keep** (confirmed 2026-08-22). They are thin *by
  design*: one FastAPI router per resource, a consistent and obvious pattern.
  Merging them would hide the router registration and make `app.py`'s
  `include_router` calls stop corresponding to files.
- **`webapp` folder layout** — `routes/` (HTTP) / `queries/` (SQL) /
  `query_agent/` (LLM). A clean separation by concern. **Keep.**
- **`importer/parsers/`** — 11 modules, one per annotation layer, with the
  dependency order declared in `__init__.py`. **Keep.**
- **JS naming** — `videoLoader.js`, `crossVideo.js` are camelCase; Python is
  snake_case. **Keep**: per-language convention is correct, and the style guide
  says so.
- **`identity_resolution.py`** — resolves a face or voice identity feature
  structure to a `person_id` *within one CAS*. The name reads as though it
  concerned cross-video identity, which is the linker's job. **Rename** to
  `person_resolution.py` (decided 2026-08-22).
- **Log prefixes** — `[duui_parser]`, `[duui_global_identity]`, `[duui_webapp]`.
  Inconsistent with each other and with the glossary's names. The style guide
  (§9) requires `[importer]`, `[identity]`, `[webapp]`. **Change here**
  (decided 2026-08-22), since the package rename touches the same lines.
- **`/api/stats` (D9)** — keep, and keep it registered as a discrepancy.

---

## 3.7 Steps, in order

Each step is one commit. **150/150 before each.** Renames never mixed with
rewrites.

| # | Step | Risk |
| --- | --- | --- |
| 1 | Group A purge **excluding** `docker-compose.yml:38` — `app.py` title and docstring, `a11y-ci.yml` paths | None |
| 2 | `git mv src/main src/importer`; update every import, the `Dockerfile` `ENTRYPOINT`, and the log prefixes | Low, wide |
| 3 | Create `importer/cas/`; move `cas_views.py` → `cas/views.py`, `typesystem.py` → `cas/typesystem.py`, `identity_resolution.py` → `cas/person_resolution.py` (§3.4b) | Low, wide |
| 4 | Split `config.py` → `config.py` + `cas/types.py` | Low |
| 5 | Split `media.py` → `cas/sofas.py` + `video_files.py` | Medium |
| 6 | `pipeline.py` → `inputs.py`; `emotions.js` math helpers (**both confirmed** 2026-08-22) | Low |
| 7 | `sidebar.css` section banners | None |
| 7b | Create `js/lib/` and `js/playback/`; update every import path (§3.4b) | Low, wide |
| 8 | **Tear down first** — `docker compose down -v`, while the old project name is still in the file | Destroys the corpus, by design |
| 9 | Rename the Compose project **and** the database (§3.1), including `.env` and `.env.example` | None, once nothing is left to orphan |
| 10 | **Rebuild and re-import** — §3.7.1 | The real test |
| 11 | Verify: row counts, all four sub-projects, suite green | — |

> **The teardown must come before the rename, not after.** Verified 2026-08-22:
> under the new project name, `docker compose` finds no containers and would
> aim `-v` at volumes named `duui-video-emotion-visualization_*` that do not
> exist. It would delete nothing, leave both `duui-bundestag-stack-*` containers
> running as orphans, and strand `duui-bundestag-stack_db_data` and
> `_video_media` on disk permanently.
>
> This plan originally had the rename at step 8 and the teardown at step 9 —
> the exact hazard §3.1(a) warns about, in the ordering of the steps written to
> avoid it. A warning in prose does not protect against a sequence that
> contradicts it.

### 3.7.1 The rebuild — recreation instead of migration

Decided 2026-08-22. Destroys the current volumes and rebuilds the corpus from
its source CAS files.

```bash
docker compose down -v
```

**Run that while `docker-compose.yml` still says `name: duui-bundestag-stack`.**
It is what removes the old containers and both old volumes. Only then rename.

```bash
docker compose up --build -d
```

Then import, in this order:

```bash
docker compose --profile import run --rm cas-to-postgres-importer
```

```bash
DUUI_INPUT_XMI_DIR=/home/max/Downloads/xmi docker compose --profile import run --rm cas-to-postgres-importer
```

```bash
docker compose --profile identity run --rm global-identity-linker
```

**What the input set contains** — checked before relying on it:

| | |
| --- | --- |
| `/home/max/Downloads/xmi` | 9 `.xmi` files, **1** `.mp4`, 1.5 GB total |
| Sample input | 1 `.xmi` + `first2.mp4` |

Only `ID2021013800…mp4` exists as a file. **The eight `teil_*.mp4.xmi` carry
their video embedded in the CAS**, which is why the directory is 1.5 GB and why
this run exercises `media.py`'s extraction path — the one that would otherwise
go untested by the sample input. That makes the rebuild a genuinely better test
than the migration it replaces.

Expected result: **10 videos**, matching Phase 0's baseline —
`first2.mp4` + `ID2021013800…mp4` + `teil_000` … `teil_007`.

Row counts to compare against Phase 0: 23 persons, 920 segments, 375,205 emotion
scores, 42,930 face detections, 8 global persons. Exact equality is not required
— `video_id` values will differ (D8), and the previous corpus was built over
several runs — but the totals should match.

Note this step is **slow**: 1.5 GB of XMI with embedded video, parsed serially.

## 3.8 Exit criteria

- [x] §3.2–§3.6 approved (2026-08-22)
- [x] Database name: `duui_video_emotion`
- [x] No Group A occurrence remains; all 17 Group C occurrences intact
- [x] Log prefixes verified: only `[importer]`, `[identity]`, `[webapp]`
- [x] Package is `importer`; image builds and runs
- [x] Splits done — `config.py` 341→116, `pipeline.py` 373→273, `emotions.js` 359→251
- [x] `importer/cas/` holds the five CAS-reading modules
- [x] `js/lib/` and `js/playback/` exist; every import path updated
- [x] Corpus rebuilt per §3.7.1 — 10 videos, **every row count matches Phase 0**
- [x] Suite at 150/150 on an empty database; the same 3 known isolation
      failures on the populated one, matching Phase 0 baselines C and B exactly

## 3.10 Rebuild result

| Table | Rebuilt | Phase 0 |
| --- | --- | --- |
| videos | 10 | 10 |
| persons | 23 | 23 |
| segments | 920 | 920 |
| emotion_scores | 375,205 | 375,205 |
| face_detections | 42,930 | 42,930 |
| face_embeddings | 330 | 330 |
| voice_embeddings | 122 | 122 |
| global_persons | 8 | 8 |

Eight of the nine CAS files carry their video embedded, and all eight were
extracted successfully — 94 MB to 145 MB each. That path is never touched by the
sample input, so this was its first real exercise since `media.py` was split
into `cas/sofas.py` and `video_files.py`.

End-to-end in the browser: `teil_007.mp4`, a file that exists only because it was
pulled out of a CAS, plays with German subtitles, all three emotion modalities
populated, three people, three cross-video matches, and a clean console.

## 3.9 The database name

**`duui_video_emotion`** (decided 2026-08-22). Appears in `.env`,
`.env.example`, `docker-compose.yml` (×5) and `schema_context.py`.
