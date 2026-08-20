"""
What the long-running jobs are doing right now.

The importer and the cross-video identity job each write a `job_runs`
row while they work (see their job_runs.py -- the writers own the
table, this only reads it). The viewer polls this so an empty dropdown
or half-imported corpus reads as "a job is still running" rather than
as a broken app.

Nothing here reports a *finished* run: the question the banner answers
is "is something happening right now", and a list of past runs is a
different feature with a different shape.
"""

import psycopg2

from ..db import get_db_connection, query

#: A run whose heartbeat is older than this is not running any more --
#: the process was killed, the container was stopped, or it lost the
#: database. The writers heartbeat about once a second, so this is
#: generous by an order of magnitude: it is meant to catch death, not
#: a slow moment.
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
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
) WITH (fillfactor = 70)
"""


def ensure_table():
    """
    Create `job_runs` if this database predates it.

    pgvector-db/schema.sql only runs when the db volume is created empty, so an
    already-populated deployment would otherwise never get the table
    and every poll would 500. Best-effort on purpose: a viewer that
    can't create it (no permission, database down at boot) must still
    start and serve everything else -- active() degrades to "nothing
    running" on its own.
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
    except Exception as exc:  # noqa: BLE001 -- never block startup
        print(f"[duui_webapp] could not ensure the job_runs table exists: {exc}")
        return False


def active():
    """
    Every job currently marked running, oldest first.

    `stale` is the interesting column: a row can say 'running' long
    after the process behind it died, because a killed job never gets
    to write its own final row. The next run of that same job cleans
    the record up (see the writers' start()), but until then this is
    what separates "working" from "died mid-run".
    """
    try:
        rows = query(
            "SELECT job_run_id, job, status, phase, progress_current, progress_total, "
            "message, started_at, heartbeat_at, "
            "EXTRACT(EPOCH FROM (now() - started_at))::float8 AS elapsed_seconds, "
            "EXTRACT(EPOCH FROM (now() - heartbeat_at))::float8 AS since_heartbeat_seconds "
            "FROM job_runs WHERE status = 'running' ORDER BY started_at"
        )
    except psycopg2.errors.UndefinedTable:
        # No job has ever run against this database and ensure_table()
        # didn't get to it. Nothing is running, which is the honest
        # answer as well as the useful one.
        return []

    for row in rows:
        row["stale"] = row["since_heartbeat_seconds"] > STALE_AFTER_SECONDS
    return rows
