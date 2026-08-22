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

The recreation is specified in §3.7 step 9.

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

### Group C — genuine references to the corpus. Keep (16 occurrences)

`linking.py`, `media.py`, `text_emotion.py`, `typesystem.py`, `config.py` × 2,
`cas_views.py` × 2, `embedding.py`, `identity_resolution.py`, `emotion.py` × 3,
`token.py`, `schema_context.py:25`, and two tests.

Every one describes the actual source material — "the real Bundestag CAS", "the
Bundestag corpus". Correct per the glossary. **A global find-and-replace would
have destroyed all sixteen**, which is why the plan required reading each file.

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
| `importer/pipeline.py` | 373 | Orchestration (`run`, `run_many`, `parse_and_insert`) plus input-path resolution (`default_input_paths`, `resolve_xmi_paths`, `describe_missing_inputs`). | **Optional split**; path resolution → `inputs.py`. Lower value. |
| `query_agent/schema_context.py` | 355 | **Not a module — a data blob.** One string constant spanning lines 23–355. "355 lines" overstates its complexity. | **Do not split.** But see §3.5. |
| `identity/linking.py` | 333 | Cohesive: every function serves cross-video matching. | **Leave.** |
| `js/panels/emotions.js` | 359 | 14 functions; rendering plus statistics (`meanScores`, `meanDimension`, `dominantOf`, `orderLabels`). | **Optional split** of the math helpers. |
| `css/sidebar.css` | 391 | **Under-sectioned, not over-long** — two section banners in 391 lines. | **Add sections first**, split only if still unwieldy. |

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
| 3 | `git mv identity_resolution.py person_resolution.py` | Low |
| 4 | Split `config.py` → `config.py` + `uima_types.py` | Low |
| 5 | Split `media.py` → sofa handling + file placement | Medium |
| 6 | Optional: `pipeline.py` → `inputs.py`; `emotions.js` math helpers | Low |
| 7 | `sidebar.css` section banners | None |
| 8 | Rename the Compose project **and** the database (§3.1), including `.env` and `.env.example` | None once §3.7.1 is accepted |
| 9 | **Rebuild and re-import** — §3.7.1 | The real test |
| 10 | Verify: row counts, all four sub-projects, suite green | — |

### 3.7.1 The rebuild — recreation instead of migration

Decided 2026-08-22. Destroys the current volumes and rebuilds the corpus from
its source CAS files.

```bash
docker compose down -v
```

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
go untested by the sample input. That makes step 9 a genuinely better test than
the migration it replaces.

Expected result: **10 videos**, matching Phase 0's baseline —
`first2.mp4` + `ID2021013800…mp4` + `teil_000` … `teil_007`.

Row counts to compare against Phase 0: 23 persons, 920 segments, 375,205 emotion
scores, 42,930 face detections, 8 global persons. Exact equality is not required
— `video_id` values will differ (D8), and the previous corpus was built over
several runs — but the totals should match.

Note this step is **slow**: 1.5 GB of XMI with embedded video, parsed serially.

## 3.8 Exit criteria

- [x] §3.2–§3.6 approved (2026-08-22)
- [ ] New database name chosen — §3.9
- [ ] No Group A occurrence remains; all 16 Group C occurrences intact
- [ ] Package is `importer`; image builds and runs
- [ ] Log prefixes are `[importer]`, `[identity]`, `[webapp]`
- [ ] Splits done; every module has one subject
- [ ] Corpus rebuilt per §3.7.1; 10 videos; totals match Phase 0
- [ ] Suite at 150/150

## 3.9 Open question

**What should the database be called?** Renaming was decided; the name was not.
It has to be settled before step 8, and it is cheap to change now and annoying
later.

Recommendation: **`duui_video_emotion`**. Short, matches the project without
restating it, and stays clear of `duui_video_emotion_visualization`, which is
accurate but long to type at every `psql` invocation. Postgres allows up to 63
characters, so either fits.

Whatever is chosen appears in `.env`, `.env.example`, `docker-compose.yml` (×5),
`schema_context.py`, and this plan.
