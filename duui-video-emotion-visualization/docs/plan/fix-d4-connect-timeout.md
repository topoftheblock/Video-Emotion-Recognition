# Fix D4 — no connect timeout in application code

Not a phase. A single defect, carried since
[Phase 0 §0.2](phase-0-baseline.md) and registered as
[D4](phase-2-ledger.md). Scheduled between Phase 5 and Phase 6 by
decision, on its own branch: `code-cleanup/fix-d4-connect-timeout`.

---

## 1. The defect, verified

`psycopg2.connect()` with no `connect_timeout` waits on the operating
system's TCP timeout. Against a host that accepts the route but never
answers, that is minutes, and nothing is printed while it waits.

Reproduced 2026-08-29 against a blackholed address:

    DUUI_DB_HOST=10.255.255.1  →  still hanging at 25s, no output

The same connection with `connect_timeout=10` fails cleanly:

    OperationalError: connection to server at "10.255.255.1", port 5432
    failed: timeout expired                         (raised at 10.0s)

Compose masks it, because the database is on the same network and
answers immediately. A wrong or firewalled `DUUI_DB_HOST` triggers it.

**Why it matters most in the webapp.** `create_app()` calls
`jobs_query.ensure_table()`, which connects. That call is already
wrapped in a broad `except`, so *with* a timeout the webapp logs a
warning and starts anyway. *Without* one it never reaches the point of
listening, so the container's healthcheck never gets a chance to report
anything either.

## 2. Scope — larger than the ledger recorded

D4 names three files. There are **five** application call sites, in
three sub-projects:

| File | Call |
| --- | --- |
| `webapp/src/backend/db.py` | `get_db_connection` |
| `cas-to-postgres-importer/src/importer/db.py` | `get_db_connection` |
| `global-identity-linker/src/identity/db.py` | `get_db_connection` |
| `cas-to-postgres-importer/src/importer/job_runs.py` | the job run's own connection |
| `global-identity-linker/src/identity/job_runs.py` | the same, in the twin |

The two `job_runs.py` connections are the ones the ledger missed. They
matter: a job that hangs there produces no progress and no error.

Four more call sites are in test code:

| File | Today |
| --- | --- |
| `webapp/tests/conftest.py` | `connect_timeout=2` on the probe; **none** on the fixture |
| `cas-to-postgres-importer/tests/conftest.py` | same |
| `global-identity-linker/tests/conftest.py` | same |
| `webapp/tests/test_emotion_series.py` | none |
| `tests/ensure_test_db.py` | `connect_timeout=10` — the existing precedent |

## 3. Approach

**Put the timeout in `DB_CONFIG`, not at each call site.** One place per
sub-project, and every connection inherits it — including the two
`job_runs.py` ones and the test fixtures, which is exactly the set that
is missing it today.

**Make it configurable, defaulting to 10 seconds.** Everything else
deployment-varying in this project is a `DUUI_*` variable, and a
connect timeout is deployment-varying: a slow or distant database is a
legitimate reason to raise it. Ten matches `tests/ensure_test_db.py`,
which is the only place in the project that already sets one.

    DUUI_DB_CONNECT_TIMEOUT, default 10

### The trap this creates, confirmed before writing this plan

All three `conftest.py` probes call:

    psycopg2.connect(**DB_CONFIG, connect_timeout=2)

Once `DB_CONFIG` carries the key, that is a duplicate keyword argument
and raises `TypeError` immediately — every database-backed test in the
project would error rather than skip. Verified.

**Resolution:** the probe keeps its own short timeout, but takes it by
overriding the dict rather than by passing a second keyword:

    psycopg2.connect(**{**DB_CONFIG, "connect_timeout": 2})

The probe's 2 seconds is deliberate and stays: it decides whether to
skip the suite, and waiting the full connect timeout to answer that
would slow every run on a machine with no database.

## 4. Steps

| # | Step |
| --- | --- |
| 1 | Add `connect_timeout` to `DB_CONFIG` in all three `config.py`, read from `DUUI_DB_CONNECT_TIMEOUT` with a default of 10 |
| 2 | Fix the three `conftest.py` probes to override rather than duplicate the keyword |
| 3 | Confirm the `job_runs.py` twins still differ only by their log prefix |
| 4 | Document the variable in `.env.example` and `docs/configuration.md` |
| 5 | Add tests: the setting is present, is an int, and is overridable |
| 6 | Verify — see §5 |
| 7 | Close D4 in the ledger and note the fix in the progress log |

## 5. Verification

- All 19 checkers green; `mypy` strict still clean on all three
  sub-projects.
- Suite 150/150, with the three probes still *skipping* rather than
  erroring when no database is reachable — checked by running the suite
  with `DUUI_DB_HOST` pointed at nothing.
- The hang is gone: with `DUUI_DB_HOST` blackholed, each of the three
  services fails with `OperationalError` in about ten seconds instead of
  hanging. Checked per service, not just once.
- The webapp **starts** against a blackholed database and serves
  `/healthz` as 503, rather than never listening at all. This is the
  behaviour the fix exists to produce, so it is checked directly.
- The stack still works normally: importer, linker and webapp against
  the real database, with row counts unchanged.
- `DUUI_DB_CONNECT_TIMEOUT=1` is honoured, proving the variable is wired
  and not just declared.

## 6. Out of scope

- **Statement timeouts.** `query_agent/sql_guard.py` already sets one
  for agent SQL. Whether ordinary queries should have one too is a
  separate question, and a wrong answer there breaks a long import.
- **Retries or backoff.** A timeout turns a hang into a clean error.
  Deciding what should then happen — retry, wait for the database, exit —
  is an operations decision, not this fix.
- **Pooling.** Untouched; `db.py` explains why there is none.

## 7. Open questions

1. **Ten seconds, or shorter?** Ten matches the existing precedent and
   tolerates a slow network. A shorter value fails faster but risks a
   false failure on a cold or loaded database. Ten unless you prefer
   otherwise.
2. **One variable, or one per service?** One (`DUUI_DB_CONNECT_TIMEOUT`)
   is proposed: all three read the same `DUUI_DB_*` settings today, and
   splitting them would be the first exception to that.
