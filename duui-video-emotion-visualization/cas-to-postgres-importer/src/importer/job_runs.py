"""Report progress into `job_runs`, so the webapp can show it.

Identical to the copy in the other job, which is deliberate:
sub-projects share no code, so this file exists twice. **Keep the two
byte-identical apart from the log prefix.** `pgvector-db/schema.sql`
carries the canonical DDL and lists every copy.

Three properties it is built around:

1. **It never breaks the job it reports on.** Progress is a convenience,
   and a job failing because the status table was missing or its status
   connection dropped would be a far worse fault than no status at all.
   Every database call here is caught, and the first failure disables
   reporting for the rest of the run, with one line on stdout so the
   silence is explained.

2. **It uses its own connection.** A caller may do its work inside a
   single long transaction, and heartbeats written on that connection
   would stay invisible until it committed — the moment they stop being
   useful. This connection is opened separately and is autocommit, so
   each heartbeat is visible immediately, and it sits outside the
   caller's transaction, so a rolled-back run still leaves an accurate
   record of having failed.

3. **It writes at most once a second.** `update()` is called from inside
   loops, and the throttle is what stops a per-item call site becoming a
   per-item write. A phase change and the final row always go through,
   so the last thing written is never stale.

A daemon thread writes a bare heartbeat every few seconds besides, so a
long stretch of work between `update()` calls is not mistaken for a dead
process.
"""

import threading
import time
from types import TracebackType
from typing import Literal

import psycopg2
from psycopg2.extensions import connection

from .config import DB_CONFIG

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

# Minimum seconds between writes from `update()`. Progress one second
# stale looks live on screen, and the webapp polls a running job every
# two seconds (POLL_ACTIVE_MS in js/panels/jobs.js).
MIN_WRITE_INTERVAL = 1.0

# Seconds between the background thread's bare heartbeats.
#
# The phases that report progress are not the phases that take the time:
# loading a large CAS is a single call that can run for minutes without
# reaching another `update()` call site. Left to the call sites alone,
# `heartbeat_at` would go stale mid-parse and the webapp would report a
# healthy job as unresponsive. Five seconds sits comfortably inside its
# staleness window (STALE_AFTER_SECONDS in
# webapp/src/backend/queries/jobs.py, currently 30).
HEARTBEAT_INTERVAL = 5.0


class JobRun:
    """One row in `job_runs`, kept up to date for the length of a run.

    Use it as a context manager:

        with JobRun("importer") as job:
            job.update(phase="parsing CAS", current=1, total=12)

    Leaving the block marks the row finished, or failed if an exception
    is propagating, so a crash is recorded as a crash rather than left
    looking like a job that is still going.
    """

    def __init__(self, job: str, min_interval: float = MIN_WRITE_INTERVAL) -> None:
        """Prepare a run. Nothing is written until `start()`.

        Args:
            job: The kind of job, stored in `job_runs.job`.
            min_interval: Seconds to throttle `update()` writes to.
        """
        self.job = job
        self.min_interval = min_interval
        self._conn: connection | None = None
        self._run_id: int | None = None
        self._disabled = False
        self._last_write = 0.0
        self._phase: str | None = None
        self._current: int | None = None
        self._total: int | None = None
        # psycopg2 connections are thread-safe, cursors are not. The
        # lock keeps the heartbeat thread and the caller's own update()
        # calls from opening cursors on this connection at the same
        # moment.
        self._lock = threading.Lock()
        self._stop_beating = threading.Event()
        self._beat_thread: threading.Thread | None = None

    # --- Lifecycle ------------------------------------------------------

    def __enter__(self) -> "JobRun":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is None:
            self.finish("finished")
        else:
            self.finish("failed", message=f"{exc_type.__name__}: {exc}")
        return False

    def start(self, phase: str | None = None) -> None:
        """Create the row and begin heartbeating."""
        try:
            self._conn = psycopg2.connect(**DB_CONFIG)
            self._conn.autocommit = True
            with self._conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
                # A run of this job that is still marked running cannot
                # actually be running — this process would not have been
                # started in its place. Closing it out here is what
                # keeps a killed job (which never got to write its own
                # final row) from showing up in the webapp forever.
                cur.execute(
                    "UPDATE job_runs SET status = 'failed', finished_at = now(), "
                    "message = COALESCE(message, "
                    "'interrupted — superseded by a later run') "
                    "WHERE job = %s AND status = 'running'",
                    (self.job,),
                )
                cur.execute(
                    "INSERT INTO job_runs (job, status, phase) "
                    "VALUES (%s, 'running', %s) RETURNING job_run_id",
                    (self.job, phase),
                )
                self._run_id = cur.fetchone()[0]
            self._phase = phase
            self._last_write = time.monotonic()
            self._start_beating()
        except Exception as exc:  # status must not break the job
            self._give_up(exc)

    def _start_beating(self) -> None:
        """Keep `heartbeat_at` fresh from a daemon thread.

        Without it the only heartbeats are the ones the caller's own
        call sites produce, and the longest phase can be a single call
        with no call sites inside it — so the webapp would report a
        healthy job as dead. Daemon, so it can never hold the process
        open.
        """
        self._stop_beating.clear()
        self._beat_thread = threading.Thread(
            target=self._beat, name="job-heartbeat", daemon=True
        )
        self._beat_thread.start()

    def _beat(self) -> None:
        """Write a bare heartbeat until told to stop."""
        while not self._stop_beating.wait(HEARTBEAT_INTERVAL):
            # Heartbeat only: phase and progress belong to whoever is
            # doing the work. `track=False` keeps these off the
            # throttle's clock, so a beat cannot swallow the caller's
            # next real update.
            self._write(
                "UPDATE job_runs SET heartbeat_at = now() WHERE job_run_id = %s",
                (self._run_id,),
                force=True,
                track=False,
            )

    def finish(self, status: str = "finished", message: str | None = None) -> None:
        """Write the final row and close the connection.

        Args:
            status: What to record, normally "finished" or "failed".
            message: A summary. Omitted, the message already on the row
                is kept.
        """
        # Stop the heartbeat first: a beat landing after the final row
        # would move heartbeat_at on a run that is already over.
        self._stop_beating.set()
        if self._beat_thread is not None:
            self._beat_thread.join(timeout=1.0)
            self._beat_thread = None

        # COALESCE so that finishing without a message keeps the summary
        # the caller already wrote, rather than blanking it at the last
        # moment.
        self._write(
            "UPDATE job_runs SET status = %s, message = COALESCE(%s, message), "
            "phase = NULL, heartbeat_at = now(), finished_at = now() "
            "WHERE job_run_id = %s",
            (status, message, self._run_id),
            force=True,
        )
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    # --- Progress -------------------------------------------------------

    def update(
        self,
        phase: str | None = None,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> None:
        """Record where the job has got to.

        Omitted arguments keep their previous value, so a loop can call
        `update(current=i)` without restating the phase each time.

        Throttled to `MIN_WRITE_INTERVAL`, except when the phase
        changes: that is what a watcher reads as "something happened"
        and is worth a write of its own.

        Args:
            force: Write regardless of the throttle. For the few call
                sites that must not be dropped, such as a final summary.
        """
        phase_changed = phase is not None and phase != self._phase
        if phase is not None:
            self._phase = phase
        if current is not None:
            self._current = current
        if total is not None:
            self._total = total

        self._write(
            "UPDATE job_runs SET phase = %s, progress_current = %s, "
            "progress_total = %s, message = COALESCE(%s, message), "
            "heartbeat_at = now() WHERE job_run_id = %s",
            (self._phase, self._current, self._total, message, self._run_id),
            force=force or phase_changed,
        )

    # --- Plumbing -------------------------------------------------------

    def _write(
        self, sql: str, params: tuple, force: bool = False, track: bool = True
    ) -> None:
        """Run one statement, unless throttled or already given up on.

        Args:
            track: Whether this write resets the throttle. False for
                heartbeats, so a beat cannot swallow the caller's next
                real update.
        """
        if self._disabled or self._conn is None or self._run_id is None:
            return
        now = time.monotonic()
        if not force and now - self._last_write < self.min_interval:
            return
        try:
            with self._lock, self._conn.cursor() as cur:
                cur.execute(sql, params)
            if track:
                self._last_write = now
        except Exception as exc:  # status must not break the job
            self._give_up(exc)

    def _give_up(self, exc: Exception) -> None:
        """Disable reporting for the rest of the run, saying so once."""
        self._disabled = True
        self._stop_beating.set()
        print(f"[importer] job status reporting disabled ({exc})")
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
