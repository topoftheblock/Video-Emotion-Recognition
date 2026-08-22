# Phase 3 — Structure: naming, splitting, merging

*Detailed plan for Phase 3. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` plan drafted 2026-08-22, awaiting approval of §3.2–§3.6.
Branch: `code-cleanup/phase-3`.

## 3.0 What this phase is for

All path-changing churn, in one place, before anything is written about those
paths. **No behavior changes.** Every step is a rename, a move, or a split; the
suite must sit at 150/150 after each.

This is the highest-risk phase in the plan, for one reason: §3.1.

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

### (b) The database name — *not* a project name

`duui_bundestag` appears as the `DUUI_DB_NAME` default in six places. It is the
name of a database **that exists inside the volume**. Changing the default means
the service connects to a database that is not there.

**Recommendation: keep `duui_bundestag`.** The glossary already says "Bundestag"
is correct for the *source material*, and this is a value describing a corpus,
not a project identifier. Renaming it buys nothing and costs a second migration
inside the volume.

### The migration, if (a) proceeds

Development data here is reproducible, so the cheap path is available — but the
procedure has to be written down regardless, because **any user who renames the
project hits this**, and their data may not be reproducible.

1. Before renaming: `pg_dump` the database, and archive the video-store volume.
2. Rename `name:` in `docker-compose.yml`.
3. `docker compose up -d` — new empty volumes are created.
4. Restore the dump; copy the video files back.
5. Verify row counts against the pre-rename numbers.
6. Remove the orphaned volumes **only after** verifying.

Steps 1–6 land in **one commit** with the rename, and the procedure is written
into `docs/operations.md` (the stub already has the heading).

> Confirmed in Phase 0: renaming a **service** (`db` → `pgvector-db`) is
> data-safe. Only the **project** name moves volumes.

---

## 3.2 The stale name purge — verified, file by file

33 occurrences. Read individually, they fall into three groups.

### Group A — the dead project name. Remove (10 occurrences)

| Where | What |
| --- | --- |
| `docker-compose.yml:38` | `name: duui-bundestag-stack` → `duui-video-emotion-visualization`. **§3.1(a) applies.** |
| `webapp/src/backend/app.py:63` | `FastAPI(title="DUUI Bundestag Video Viewer")` — **user-facing**, and carries the retired word "Viewer" too. → `"DUUI Video Emotion Visualization"` |
| `webapp/src/backend/app.py:2` | Module docstring, "DUUI Bundestag pipeline" |
| `webapp/docs/a11y-ci.yml` | 6 × `duui-bundestag-stack/` in `paths:` filters and `working-directory:`. Repoint at `duui-video-emotion-visualization/`. **Still not activated** (Phase 7 also fixes its false "no CI" premise). |

### Group B — the database name. Keep (7 occurrences)

`.env.example:60`, `docker-compose.yml` × 5, `schema_context.py:15`. See §3.1(b).

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

**Recommendation: rename.**

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

**Check before starting:** confirm no installed distribution provides a
top-level `importer` module that could shadow it.

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
  `routes/jobs.py` (23). **Keep.** They are thin *by design*: one FastAPI router
  per resource, a consistent and obvious pattern. Merging them would hide the
  router registration.
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
  `person_resolution.py`.
- **Log prefixes** — `[duui_parser]`, `[duui_global_identity]`, `[duui_webapp]`.
  Inconsistent with each other and with the glossary's names. The style guide
  (§9) requires `[importer]`, `[identity]`, `[webapp]`. **Change here**, since
  the package rename touches the same lines.
- **`/api/stats` (D9)** — keep, and keep it registered as a discrepancy.

---

## 3.7 Steps, in order

Each step is one commit. **150/150 before each.** Renames never mixed with
rewrites.

| # | Step | Risk |
| --- | --- | --- |
| 1 | Approve §3.2–§3.6 | — |
| 2 | Group A purge **excluding** `docker-compose.yml:38` — `app.py` title and docstring, `a11y-ci.yml` paths | None |
| 3 | Confirm no `importer` shadowing; `git mv src/main src/importer`; update imports, `Dockerfile`, log prefixes | Low, wide |
| 4 | `git mv identity_resolution.py person_resolution.py` | Low |
| 5 | Split `config.py` → `config.py` + `uima_types.py` | Low |
| 6 | Split `media.py` → sofa handling + file placement | Medium |
| 7 | Optional: `pipeline.py` → `inputs.py`; `emotions.js` math helpers | Low |
| 8 | `sidebar.css` section banners | None |
| 9 | **The Compose project rename + volume migration**, one commit, procedure into `docs/operations.md` | **High — §3.1** |
| 10 | Full verification: rebuild, all four sub-projects exercised, row counts match | — |

Step 9 is deliberately last: everything before it is reversible with `git
revert`, and there is no reason to carry the one destructive step through eight
other changes.

## 3.8 Exit criteria

- [ ] §3.2–§3.6 approved
- [ ] No Group A occurrence remains; all 16 Group C occurrences intact
- [ ] Package is `importer`; image builds and runs
- [ ] Splits done; every module has one subject
- [ ] Volume migration executed **and documented** in `docs/operations.md`
- [ ] All four sub-projects exercised after the rename; row counts match Phase 0
- [ ] Suite at 150/150
