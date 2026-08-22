# Phase 0 — Baseline and safety net

*Detailed plan for Phase 0. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md) — this file holds only the
working detail and results for this phase.*

Status: `[~]` in progress. Environment survey done 2026-08-22; all four
decisions in 0.3 answered the same day.

## 0.0 What this phase is for

Every later phase is a large-scale edit. Phase 0 produces the reference that
tells a regression apart from a pre-existing failure. It changes no source code.

## 0.1 Environment survey — done

| Fact | Value |
| --- | --- |
| Python | 3.12.3 (`/usr/bin/python3`) |
| `.venv/` at repo root | Exists, 77 packages — `pytest`, `dkpro-cassis` 0.11.1, `fastapi` 0.141.1, `dotenv`, `psycopg2`. Usable as-is. |
| System `pytest` | **Not installed.** Every command must go through `.venv/bin/python -m pytest`, never a bare `pytest`. |
| Docker | 29.7.2, working |
| Stack state | **Running right now** — `duui-bundestag-stack-webapp-1` and `duui-bundestag-stack-db-1`, both healthy, up ~2h |
| Database contents | **Real imported data**: 10 videos, 23 persons, 920 segments, **375,205 emotion scores**, 42,930 face detections, 8 global persons, 3 job runs. All 14 tables present. |
| Volumes | `duui-bundestag-stack_db_data` (created 2026-08-20), `duui-bundestag-stack_video_media` |

## 0.2 Blocking findings

**(a) Renaming the compose project would orphan the database.** `docker-compose.yml`
line 38 reads `name: duui-bundestag-stack`, and Compose derives named-volume
names from the project name — hence `duui-bundestag-stack_db_data`. The
`bundestag` purge in Phase 3 touches that line. The moment it changes,
`docker compose up` creates a **new, empty** `<newname>_db_data`, the existing
375k-row database is orphaned, and it presents exactly as data loss.

The distinction that matters, because it is easy to get backwards:

- Renaming a **service** (`db` → `pgvector-db`, already done in the file) is
  safe. Volumes are unaffected.
- Renaming the **project** (`name:`) is **not** safe. It re-points every named
  volume.

Phase 3 therefore needs an explicit volume-migration step — `pg_dump` and
restore into the new volume, or a volume-to-volume copy — and it must be planned,
not improvised. Recorded in §2 and to be carried into Phase 3's detailed plan.

**(b) The running containers predate the current compose file.** The database
container is `duui-bundestag-stack-db-1`, i.e. from a `db:` service; the compose
file now declares `pgvector-db:`. So what is running was started from an older
revision. A `docker compose up -d` today would build the renamed service
alongside the old container rather than replacing it. Harmless for data (same
project name, same volume) but it means **the running stack is not evidence that
the current source works.** Phase 0 must rebuild from source to establish that.

**(c) On the host, every DB-backed test skips.** All `DUUI_DB_*` lines in `.env`
are commented out, so `config.py` falls back to its placeholder defaults
(`your_db` / `your_user` / `your_password`), the connection fails, and each
DB-backed test skips. Compose passes real values (`duui_bundestag` / `duui` /
`duui`) to containers only.

The skip messages are clear if you look for them, so "silent" overstates it —
but the run still **reports success having executed only the pure-function
tests**, which is the failure mode Phase 6 exists to remove. Phase 0 must
therefore record two separate baselines: with a database and without one. A
single number would be meaningless.

## 0.3 Decisions — answered 2026-08-22

| # | Question | Answer |
| --- | --- | --- |
| 1 | Run the suites against the live database? | **Yes.** |
| 2 | Is the dataset precious? | **No — reproducible by the user.** The running stack is a *test* stack; nothing in it matters. |
| 3 | Tear down and rebuild the containers? | **Yes.** |
| 4 | Put real `DUUI_DB_*` values in host `.env`? | **Yes, for now** — superseded by testcontainers in Phase 6. |

**Consequence for Phase 3, and it is a good one:** the volume-orphaning hazard
(0.2a) is a *procedural* problem, not a data-loss one. The 375k rows can be
regenerated, so the compose-project rename does not need a verified migration of
irreplaceable data. It still needs to be **deliberate** — someone must decide
between migrating the volume and re-importing, rather than discovering the
choice was made for them by a rename. The hazard stays documented; its severity
drops from "could destroy work" to "could waste an afternoon".

## 0.4 Snapshot — reduced scope

Decision 2 removes the need for a verified, restorable backup: the data is
reproducible and disposable. The full ceremony (verify-restore into a scratch
database, record locations, treat as irreplaceable) is **dropped**.

What is still worth doing, purely as convenience:

- A single `pg_dump` to the scratchpad, so a mangled test run can be undone in
  seconds instead of re-imported. Cheap insurance, not a safety net.
- Record the current row counts (0.1) so a later unexplained change is
  detectable.

No restore verification. If the dump turns out to be bad, the fallback is
re-importing from the sample input, which is the documented path anyway.

## 0.5 Baseline — established 2026-08-22

### The three baselines

Run via `.venv/bin/python -m pytest` from the repository root (all three suites).

| Scenario | Result | Time |
| --- | --- | --- |
| **A** — no database (placeholder credentials) | 121 passed, 29 skipped | 0.9s |
| **B** — the populated live database | 147 passed, **3 failed** | 1.6s |
| **C** — empty database, `schema.sql` applied | **150 passed, 0 skipped, 0 failed** | 1.4s |

**Baseline C is the reference.** A green run is 150/150. Baseline B's failures are
explained below and are not code defects; baseline A's 29 skips are the
DB-backed tests declining to run.

### Finding 1 (major) — the DB tests are not isolated from existing data

All three baseline-B failures share one root cause: **the DB-backed tests assume
an empty database**, and the live one holds real imported rows.

- `test_deleting_a_video_takes_its_whole_subtree` — the fixture inserts videos
  named `teil_000.mp4` and `teil_001.mp4`, **which already exist** as `video_id`
  3 and 4 with real persons attached. The test expects 1 person row and finds 4.
- `test_recompute_writes_global_person_match_score` and
  `test_global_person_match_score_is_order_independent` — both expect the
  synthetic person P2's nearest cross-video centroid to sit at distance 2.0, and
  get 0.987. The database holds **330 real face embeddings across 33 persons**,
  which supply nearer neighbours than the fixtures do.

**Proof:** the same suite on an empty schema-applied database is 150/150
(baseline C). Nothing is wrong with the code.

This is a **test-isolation defect**, and it is exactly what Phase 6's
testcontainers decision fixes — now demonstrated rather than predicted. It also
sharpens the requirement: an isolated database is not a convenience for
developers without Postgres, it is what makes the DB-backed tests *correct at
all*. Run against a populated database today, they report false failures.

### Finding 2 — no `connect_timeout` anywhere in application code

`create_app()` calls `jobs_query.ensure_table()`, which calls
`get_db_connection()` → `psycopg2.connect(**DB_CONFIG)` with no timeout
(`webapp/src/backend/db.py`). Against a host that **blackholes** packets rather
than refusing them, this blocks forever: the webapp hangs at startup with no
diagnostic and no error.

Found by accident — an early attempt at baseline A pointed `DUUI_DB_HOST` at an
unroutable address and `test_routes.py` hung past five minutes, while collection
took 0.7s. Only the test `conftest.py` files set `connect_timeout=2`; no
application module does.

Compose masks it, because `pgvector-db` either resolves or fails DNS quickly. The
real-world trigger is a wrong or firewalled database IP. **Not fixed** — Phase 0
changes no source. Logged for Phase 2's ledger; the fix is small (a
`connect_timeout` in `DB_CONFIG`) but the value is a judgement call and it is a
behaviour change.

### Finding 3 — stale `__pycache__` made every traceback unreadable

The first populated-database run produced tracebacks with `???` for source lines
and paths that do not exist: `/w/duui-video-emotion-cas-to-postgres/...` (a
container mount) and `.../duui-bundestag-stack/...` (the pre-rename directory
name). Compiled bytecode keeps the `co_filename` it was first compiled under, so
pytest could not find the sources to display.

Cleared with `find . -name __pycache__ -exec rm -rf {} +`, after which tracebacks
were readable and the diagnosis above was possible. Harmless, but worth knowing:
**after Phase 3's renames, clear `__pycache__` before trusting a traceback.**

### Finding 4 — the importer announces work it then skips

`pipeline.py:207` prints `Loading CAS data from <file>...` *before* the
already-imported check at `:227`; the real `load_cas_from_xmi` call is at `:253`.
A skipped file therefore prints:

```
Loading CAS data from /data/input/xmi/full_2sek_with_person.xmi...
[duui_parser] 'first2.mp4' is already imported (video_id 1) -- skipping.
```

The *behaviour* matches the documentation — the CAS genuinely is not loaded, only
the raw XML is parsed to read the filename — but the *message* says otherwise.
A user-facing string defect for Phase 5, which owns log and CLI output. Worth
checking in Phase 2 whether "nearly free" still holds for the large embedded-video
CAS files the README describes, since the XML tree is still parsed in full.

### Stack rebuild — verified

- `docker compose down --remove-orphans` → `build` → `up -d`: both services
  healthy. **Volumes preserved, data intact** (10 videos, 375,205 emotion scores).
- The `db` → `pgvector-db` service rename took effect — the container is now
  `duui-bundestag-stack-pgvector-db-1`. **This confirms 0.2's analysis in
  practice: renaming a service is data-safe; renaming the project is not.**
- `webapp` — `/healthz` returns ok, `/api/videos` returns the ten videos.
- `cas-to-postgres-importer` — the default skip path and the
  `--on-existing replace` full-parse path both complete successfully.
- `global-identity-linker` — recomputed 23 persons into 8 global identities
  (21 linked).

All four sub-projects exercised. No quickstart deviations found in the paths
taken; the README's fuller claims remain unverified and belong to Phase 2.

### Environment notes for anyone continuing

- **There is no system `pytest`.** Always `.venv/bin/python -m pytest`.
- `.env` now has `DUUI_DB_NAME`/`USER`/`PASSWORD`/`HOST` uncommented (decision 4),
  which is what makes baseline B reachable from the host.
- A 31 MB `pg_dump` of the pre-Phase-0 database sits in the session scratchpad as
  `baseline-db.sql`. Convenience only, per 0.4 — not a verified backup.
- Baseline C is reproducible: `CREATE DATABASE duui_baseline_test`, apply
  `pgvector-db/schema.sql`, then run with `DUUI_DB_NAME=duui_baseline_test`.

## 0.6 Working method

Agreed 2026-08-22:

- **`code-cleanup/phase-<N>`**, branched off **`code-cleanup/main`** and merged
  back into it with `--no-ff` when the phase closes. `code-cleanup/main` reaches
  `main` only at the very end. No branch may be named plain `code-cleanup`: git
  cannot hold both a `code-cleanup` ref file and a `code-cleanup/` ref
  directory. `code-cleanup` reaches
  `main` only at the end of the whole pass. Phases are strictly sequential, so
  branching off `code-cleanup` rather than `main` means each phase starts on top
  of finished work.
- One commit per logical step; renames never mixed with rewrites.
- Baseline C green (150/150) before each commit.
- **No AI attribution in commits or in any file produced** — see §5 of the plan
  overview.

## 0.7 Exit criteria

- [x] Snapshot taken (reduced scope per decision 2) — `baseline-db.sql`, 31 MB
- [x] Baselines recorded per suite: **A** no DB, **B** live DB, **C** empty DB
- [x] Stack rebuilt from current source and confirmed healthy
- [x] Import path exercised — both `skip` and `--on-existing replace`
- [x] Identity linker exercised
- [x] Findings logged for Phase 2 (findings 2 and 4) and Phase 6 (finding 1)
- [x] `plan.md` committed, and since split into `docs/plan/`
- [x] Branch convention agreed: `code-cleanup/phase-<N>` off `code-cleanup`

**Phase 0 is complete.** The reference for every later phase is
**baseline C: 150 passed, 0 skipped, 0 failed.**

## 0.8 What this hands to later phases

| To | What |
| --- | --- |
| Phase 2 | Findings 2 and 4 as ledger entries; the README's unverified claims |
| Phase 3 | Confirmed in practice: service renames are data-safe, the project rename is not; clear `__pycache__` after renaming |
| Phase 5 | Finding 4 — the importer's misleading skip message |
| Phase 6 | Finding 1, with proof: the DB tests are incorrect against a populated database, not merely skippable |
