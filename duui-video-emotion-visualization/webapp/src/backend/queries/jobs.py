"""What the long-running jobs are doing right now.

The importer and the identity linker each write a `job_runs` row while
they work. They own that table; this only reads it. The webapp polls
this so that an empty dropdown, or a corpus that is only half imported,
reads as "a job is still running" rather than as a broken app.

Nothing here reports a *finished* run. The question the banner answers
is whether something is happening now, and a list of past runs is a
different feature with a different shape.
"""

from typing import Any

import psycopg2

from ..db import get_db_connection, query

Row = dict[str, Any]

#: A run whose heartbeat is older than this is no longer running: the
#: process was killed, the container stopped, or it lost the database.
#: The writers beat every five seconds from a background thread, so
#: this is six missed beats — enough to catch death rather than a slow
#: moment.
STALE_AFTER_SECONDS = 30

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS job_runs (
    job_run_id BIGSERIAL PRIMARY KEY,
    job TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT,
    progress_current INT,
    progress_total INT,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
) WITH (fillfactor = 70)
"""


def ensure_table() -> bool:
    """Create `job_runs` if this database predates it.

    `pgvector-db/schema.sql` only runs when the database volume is
    created empty, so an already-populated deployment would otherwise
    never get the table, and every poll would fail.

    Best-effort on purpose: a webapp that cannot create it — no
    permission, or the database down at boot — must still start and
    serve everything else. `active` degrades to "nothing running" on
    its own.

    Returns:
        Whether the table is now known to exist.
    """
    try:
        conn = get_db_connection()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
        finally:
            conn.close()
        return True
    except Exception as exc:  # must never block startup
        print(f"[webapp] could not ensure the job_runs table exists: {exc}")
        return False


def active() -> list[Row]:
    """Return every job currently marked running, oldest first.

    `stale` is the interesting column. A row can say `running` long
    after the process behind it died, because a killed job never gets
    to write its own final row. The next run of that same job cleans
    the record up, but until then this is what separates "working" from
    "died mid-run".

    Returns:
        One row per running job, each with elapsed and heartbeat ages
        and a `stale` flag.
    """
    try:
        rows = query(
            "SELECT job_run_id, job, status, phase, progress_current, progress_total, "
            "message, started_at, heartbeat_at, "
            "EXTRACT(EPOCH FROM (now() - started_at))::float8 AS elapsed_seconds, "
            "EXTRACT(EPOCH FROM (now() - heartbeat_at))::float8 "
            "AS since_heartbeat_seconds "
            "FROM job_runs WHERE status = 'running' ORDER BY started_at"
        )
    except psycopg2.errors.UndefinedTable:
        # No job has ever run against this database, and `ensure_table`
        # did not get to it. Nothing is running, which is the honest
        # answer as well as the useful one.
        return []

    for row in rows:
        row["stale"] = row["since_heartbeat_seconds"] > STALE_AFTER_SECONDS
    return rows
