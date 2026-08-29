"""Tests for the job run: the row the webapp reads while work happens.

This file exists in both sub-projects because `job_runs.py` does. The
two copies of that module are byte-identical apart from their log
prefix, and these two test files are kept the same way: a change to one
belongs in the other. Sub-projects share no files by design, so the
duplication is deliberate.

What is worth testing is not the happy path, which the linker's own run
covers by opening a run whenever it works. It is the three behaviours
that appear only when something goes wrong or takes a long time:

- **The throttle.** `update` is called from inside loops. Without it, a
  per-item call site becomes a per-item write.
- **The recovery.** A killed job never writes its own final row, so the
  next run of the same job closes the stale one out. Without that, the
  webapp shows a job running forever.
- **The refusal to break its caller.** Reporting is a convenience; a
  job must not fail because its status table would not take a write.

Database-backed. Each test cleans up the rows it made.
"""

from collections.abc import Iterator

import pytest

from identity.db import get_db_connection
from identity.job_runs import JobRun

JOB = "zz-job-runs-test"


@pytest.fixture
def clean_job_rows(db_available: bool) -> Iterator[None]:
    """Remove every row this test job leaves behind, before and after.

    Named distinctively so a row left by a crashed run is recognisable,
    and so this can never touch a real job's row.
    """
    if not db_available:
        pytest.skip("no database available")

    def purge() -> None:
        """Delete every row belonging to this test job."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM job_runs WHERE job = %s", (JOB,))
            conn.commit()
        finally:
            conn.close()

    purge()
    try:
        yield
    finally:
        purge()


def _rows() -> list[tuple]:
    """Every row this test job has, oldest first."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT job_run_id, status, phase, progress_current, message "
                "FROM job_runs WHERE job = %s ORDER BY job_run_id",
                (JOB,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def test_a_run_opens_and_closes_around_its_block(clean_job_rows: None) -> None:
    """The context manager is the whole lifecycle."""
    with JobRun(JOB) as job:
        job.update(phase="working")
        during = _rows()

    assert [r[1] for r in during] == ["running"]
    assert during[0][2] == "working"
    assert [r[1] for r in _rows()] == ["finished"]


def test_a_failing_block_is_recorded_as_failed(clean_job_rows: None) -> None:
    """A job that raises must not be left looking successful."""
    with pytest.raises(ValueError), JobRun(JOB):
        raise ValueError("the work failed")

    rows = _rows()
    assert [r[1] for r in rows] == ["failed"]
    assert "the work failed" in (rows[0][4] or "")


def test_the_exception_is_not_swallowed(clean_job_rows: None) -> None:
    """Reporting a failure must not turn it into a success."""
    with pytest.raises(RuntimeError):
        with JobRun(JOB):
            raise RuntimeError("must propagate")


def test_progress_writes_are_throttled(clean_job_rows: None) -> None:
    """A per-item call site must not become a per-item write.

    `start` primes the throttle, so with an interval longer than the
    test none of the twenty calls reaches the database and the column
    stays as the row was created: null.
    """
    with JobRun(JOB, min_interval=60.0) as job:
        for index in range(20):
            job.update(current=index, total=20)
        current = _rows()[0][3]

    assert current is None


def test_a_phase_change_is_never_throttled(clean_job_rows: None) -> None:
    """The phase is what the banner shows, so it must not lag."""
    with JobRun(JOB, min_interval=60.0) as job:
        job.update(phase="first")
        job.update(phase="second")
        phase = _rows()[0][2]

    assert phase == "second"


def test_the_final_row_is_never_throttled(clean_job_rows: None) -> None:
    """What is written last must be what the run really ended on."""
    with JobRun(JOB, min_interval=60.0) as job:
        job.update(current=1, total=3)
        job.update(current=3, total=3, message="all done", force=True)

    rows = _rows()
    assert rows[0][3] == 3
    assert rows[0][4] == "all done"


def test_a_stale_running_row_is_closed_by_the_next_run(clean_job_rows: None) -> None:
    """A killed job leaves a row saying `running` forever, until this.

    Simulated by opening a run and abandoning it without closing, which
    is what a killed process leaves behind.
    """
    abandoned = JobRun(JOB)
    abandoned.start(phase="interrupted")
    assert [r[1] for r in _rows()] == ["running"]

    with JobRun(JOB):
        pass

    statuses = [r[1] for r in _rows()]
    assert statuses == ["failed", "finished"], (
        "the stale row should be closed out, and the new one finished"
    )
    assert "superseded" in (_rows()[0][4] or "")


def test_reporting_failures_do_not_break_the_caller(
    clean_job_rows: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A status table that will not take a write must not fail the job.

    The whole point of the class: progress is a convenience, and a job
    failing because it could not report would be a worse fault than no
    report at all.
    """
    import identity.job_runs as module

    def refuse(**_kwargs: object) -> object:
        """Fail the way an unreachable host does."""
        raise OSError("no route to the database")

    monkeypatch.setattr(module.psycopg2, "connect", refuse)

    with JobRun(JOB) as job:
        job.update(phase="working", current=1, total=2)

    # Undone before reading back: the patch is on the shared psycopg2
    # module, so it would refuse this suite's own connection too.
    monkeypatch.undo()

    assert _rows() == []
    assert "disabled" in capsys.readouterr().out
