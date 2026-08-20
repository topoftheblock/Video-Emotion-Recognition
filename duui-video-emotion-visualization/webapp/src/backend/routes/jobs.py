"""Whether the importer or the identity job is running right now."""

from fastapi import APIRouter

from ..queries import jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def running_jobs():
    """
    The jobs currently working, for the viewer's status banner.

    Polled every few seconds by every open tab, so it stays one small
    query over a table with one row per run -- and returns 200 with an
    empty list rather than a 404 when nothing is running, since "no
    jobs" is the normal answer and not an error.
    """
    return {
        "jobs": jobs.active(),
        "stale_after_seconds": jobs.STALE_AFTER_SECONDS,
    }
