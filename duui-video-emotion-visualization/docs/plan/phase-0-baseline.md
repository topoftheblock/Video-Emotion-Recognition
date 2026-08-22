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

## 0.5 Establish the baseline

- Run each suite separately and together, via `.venv/bin/python -m pytest`.
  Record pass / fail / skip **per suite**, both without a database and with one.
- For every failure or skip, record whether it is environmental or a genuine
  defect. Genuine defects follow the §5 bug rule — note, and stop to ask if the
  fix is not obvious.
- Rebuild the stack from current source (`docker compose build`, then `up`) and
  confirm it comes up healthy. Note every place the documented quickstart does
  not match what actually happens — that feeds Phase 2's discrepancy list.
- Exercise the import path once against the committed sample input
  (`cas-to-postgres-importer/src/resources/sample-input/`) so the importer is
  covered by the baseline too, not just the webapp.
- Write all of it into this section as the reference for "did we break it".

## 0.6 Working method

- Branch per phase, off `main`; one commit per logical step.
- Suites green — or green-with-known-baseline-failures — before each commit.
- Currently on branch `code-cleanup` with `plan.md` untracked. Commit the plan
  first, so the phases have a recorded starting point.

## 0.7 Exit criteria

- [ ] Verified, restorable backup of database and video volume
- [ ] Both baselines recorded (with and without a database), per suite
- [ ] Stack rebuilt from current source and confirmed healthy
- [ ] Import path exercised once against the sample input
- [ ] Quickstart deviations logged for Phase 2
- [ ] Branch convention agreed; `plan.md` committed
