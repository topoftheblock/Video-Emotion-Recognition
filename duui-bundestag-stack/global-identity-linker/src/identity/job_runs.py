"""
Writes this job's progress to `job_runs`, so the viewer can show that
the cross-video identity job is running and how far along it is.

Three properties this module is built around:

1. **It never breaks the job.** Reporting progress is a convenience;
   a recompute that fails because the status table was missing or the
   status connection dropped would be a much worse bug than no status
   at all. Every database call here is caught, and the first failure
   disables the reporter for the rest of the run (with one line on
   stdout so it isn't silent).

2. **It needs its own connection.** This job does its whole
   wipe-and-rebuild in a single transaction that commits at the very
   end, so heartbeats written on *that* connection would stay
   invisible until the moment they stopped being useful. This one is
   opened separately for the run and is autocommit, so each heartbeat
   is visible to the viewer immediately -- and it stays outside the
   job's transaction, so a rolled-back run still leaves an accurate
   record of having failed.

3. **It writes at most once a second.** update() is called from inside
   loops; the throttle is what keeps a per-item call site from turning
   into a per-item commit. A phase change and the final row always go
   through regardless, so the last thing written is never stale.

Alongside those, a daemon thread writes a bare heartbeat every few
seconds, so a long stretch of work between update() call sites is not
mistaken for a dead process.

The DDL is repeated here rather than shared because each service is
built from its own directory with nothing pulled in from the rest of
the stack (see this repo's Dockerfiles). pgvector-db/schema.sql carries the
canonical copy and lists the others.
"""

import threading
import time

import psycopg2

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
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
) WITH (fillfactor = 70)
"""

#: Seconds between heartbeat writes. Progress that is one second stale
#: is indistinguishable from live on screen, and the viewer polls no
#: faster than every two seconds anyway.
MIN_WRITE_INTERVAL = 1.0

#: Seconds between the background thread's bare heartbeats.
#:
#: The phases that report progress are not the phases that take the
#: time: loading a 170 MB CAS is a single lxml call that can run for
#: minutes without the job reaching another update() call site. Left to
#: the call sites alone, `heartbeat_at` would go stale mid-parse and
#: the viewer would report a perfectly healthy import as having
#: stopped responding. This thread's only job is to keep saying "the
#: process is alive" while the work happens elsewhere -- comfortably
#: inside the viewer's staleness window (jobs.py:STALE_AFTER_SECONDS).
HEARTBEAT_INTERVAL = 5.0


class JobRun:
    """
    One run of one job. Use it as a context manager:

        with JobRun("importer") as job:
            job.update(phase="parsing CAS", current=1, total=12)

    Leaving the block marks the row finished, or failed if an
    exception is propagating -- so a crash is recorded as a crash
    rather than left looking like a job that is still going.
    """

    def __init__(self, job, min_interval=MIN_WRITE_INTERVAL):
        self.job = job
        self.min_interval = min_interval
        self._conn = None
        self._run_id = None
        self._disabled = False
        self._last_write = 0.0
        self._phase = None
        self._current = None
        self._total = None
        # psycopg2 connections are thread-safe, cursors are not; the
        # lock is what keeps the background heartbeat and the job's own
        # update() calls from opening cursors on the same connection at
        # the same moment.
        self._lock = threading.Lock()
        self._stop_beating = threading.Event()
        self._beat_thread = None

    # -- lifecycle ----------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.finish("finished")
        else:
            self.finish("failed", message=f"{exc_type.__name__}: {exc}")
        return False

    def start(self, phase=None):
        try:
            self._conn = psycopg2.connect(**DB_CONFIG)
            self._conn.autocommit = True
            with self._conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
                # A run of this job that is still marked running cannot
                # actually be running -- this process would not have
                # been started in its place. Closing it out here is what
                # keeps a killed job (which never got to write its own
                # final row) from showing up in the viewer forever.
                cur.execute(
                    "UPDATE job_runs SET status = 'failed', finished_at = now(), "
                    "message = COALESCE(message, 'interrupted -- superseded by a later run') "
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
        except Exception as exc:  # noqa: BLE001 -- status must not break the job
            self._give_up(exc)

    def _start_beating(self):
        """
        Keep `heartbeat_at` fresh from a daemon thread.

        Without this the only heartbeats are the ones the job's own
        call sites produce, and the phase that takes the longest --
        loading a large CAS -- is a single call with no call sites
        inside it at all. The viewer would then report a healthy import
        as dead 30 seconds into every real file. Daemon, so it can
        never hold the process open.
        """
        self._stop_beating.clear()
        self._beat_thread = threading.Thread(
            target=self._beat, name="job-heartbeat", daemon=True
        )
        self._beat_thread.start()

    def _beat(self):
        while not self._stop_beating.wait(HEARTBEAT_INTERVAL):
            # Heartbeat only: phase and progress belong to whoever is
            # doing the work. `track=False` keeps these off the
            # throttle's clock, so a beat can't swallow the job's next
            # real update.
            self._write(
                "UPDATE job_runs SET heartbeat_at = now() WHERE job_run_id = %s",
                (self._run_id,),
                force=True,
                track=False,
            )

    def finish(self, status="finished", message=None):
        # Stop the heartbeat first: a beat landing after the final row
        # would move heartbeat_at on a run that is already over.
        self._stop_beating.set()
        if self._beat_thread is not None:
            self._beat_thread.join(timeout=1.0)
            self._beat_thread = None

        # COALESCE, so finishing without a message of its own keeps the
        # summary the job already wrote ("3 imported, 1 failed") rather
        # than blanking it at the last moment.
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
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    # -- progress -----------------------------------------------------

    def update(self, phase=None, current=None, total=None, message=None, force=False):
        """
        Record where the job is. Omitted arguments keep their previous
        value, so a loop can call update(current=i) without restating
        the phase every time.

        Throttled to MIN_WRITE_INTERVAL, except when the phase changes
        -- that is the part a watcher reads as "something happened",
        and it is worth a write of its own. `force` is for the handful
        of call sites that must not be dropped, like a final summary.
        """
        phase_changed = phase is not None and phase != self._phase
        if phase is not None:
            self._phase = phase
        if current is not None:
            self._current = current
        if total is not None:
            self._total = total

        self._write(
            "UPDATE job_runs SET phase = %s, progress_current = %s, progress_total = %s, "
            "message = COALESCE(%s, message), heartbeat_at = now() WHERE job_run_id = %s",
            (self._phase, self._current, self._total, message, self._run_id),
            force=force or phase_changed,
        )

    # -- plumbing -----------------------------------------------------

    def _write(self, sql, params, force=False, track=True):
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
        except Exception as exc:  # noqa: BLE001 -- status must not break the job
            self._give_up(exc)

    def _give_up(self, exc):
        self._disabled = True
        self._stop_beating.set()
        print(f"[duui_global_identity] job status reporting disabled ({exc})")
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None
