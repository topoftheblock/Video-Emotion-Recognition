"""Tests for the job-status read side.

The writers live in the other two services. What matters here is that
the webapp reads their rows the way the banner needs — in particular
that a run whose heartbeat stopped is reported as stale rather than as
still working, which is the one thing a plain "status = running" check
can never tell you.

Database-backed, so these skip when there is no database.
"""

from collections.abc import Callable, Iterator

import pytest

from backend.db import get_db_connection
from backend.queries import jobs


@pytest.fixture
def job_rows(db_available: bool) -> Iterator[Callable[..., int]]:
    """Insert job runs, and delete exactly those again afterwards.

    The rows are committed rather than held in a transaction, because
    the reader under test opens its own connection and could not see
    them otherwise. Cleanup is therefore an explicit delete.

    The table is created first if this database predates it.
    """
    if not db_available:
        pytest.skip("no database available")

    jobs.ensure_table()

    conn = get_db_connection()
    inserted = []

    def insert(
        job: str,
        status: str = "running",
        heartbeat_age_seconds: int = 0,
        **columns: object,
    ) -> int:
        """Insert one run and return its id."""
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO job_runs (job, status, phase, progress_current, "
                "progress_total, message, heartbeat_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, now() - make_interval(secs => %s)) "
                "RETURNING job_run_id",
                (
                    job,
                    status,
                    columns.get("phase"),
                    columns.get("progress_current"),
                    columns.get("progress_total"),
                    columns.get("message"),
                    heartbeat_age_seconds,
                ),
            )
            inserted.append(cur.fetchone()[0])
        conn.commit()
        return inserted[-1]

    yield insert

    # Only the rows this test made: a real run may be going on in
    # parallel, and the suite has no business deleting its row.
    if inserted:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM job_runs WHERE job_run_id = ANY(%s)", (inserted,))
        conn.commit()
    conn.close()


def test_a_running_job_is_reported_with_its_progress(
    job_rows: Callable[..., int],
) -> None:
    """A running job comes back with its phase and its counters."""
    run_id = job_rows(
        "importer",
        phase="inserting emotion (9/10)",
        progress_current=3,
        progress_total=12,
    )

    row = next(j for j in jobs.active() if j["job_run_id"] == run_id)
    assert row["job"] == "importer"
    assert row["phase"] == "inserting emotion (9/10)"
    assert (row["progress_current"], row["progress_total"]) == (3, 12)
    assert row["stale"] is False
    assert row["elapsed_seconds"] >= 0


def test_a_job_whose_heartbeat_stopped_is_reported_stale(
    job_rows: Callable[..., int],
) -> None:
    """A row still marked running reads as stale once the beat stops.

    A killed process never gets to write its own final row, so the age
    of the heartbeat is the only evidence that it is gone.
    """
    run_id = job_rows("importer", heartbeat_age_seconds=jobs.STALE_AFTER_SECONDS + 5)

    row = next(j for j in jobs.active() if j["job_run_id"] == run_id)
    assert row["stale"] is True
    assert row["since_heartbeat_seconds"] > jobs.STALE_AFTER_SECONDS


def test_finished_jobs_are_not_reported(job_rows: Callable[..., int]) -> None:
    """The banner answers what is happening now, not what has been."""
    run_id = job_rows("global-identity", status="finished")

    assert all(j["job_run_id"] != run_id for j in jobs.active())
