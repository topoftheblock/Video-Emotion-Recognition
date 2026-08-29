"""Whether the importer or the identity linker is running right now."""

from typing import Any

from fastapi import APIRouter

from ..queries import jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def running_jobs() -> dict[str, Any]:
    """Report the jobs currently working, for the status banner.

    Polled every couple of seconds by every open tab while a job runs,
    so it stays one small query over a table with one row per run. It
    answers 200 with an empty list rather than 404 when nothing is
    running, since "no jobs" is the normal answer and not an error.

    Returns:
        The running jobs, and the age at which one counts as stale.
    """
    return {
        "jobs": jobs.active(),
        "stale_after_seconds": jobs.STALE_AFTER_SECONDS,
    }
