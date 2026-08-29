"""Fixed emotion statistics for one video."""

from typing import Any

from fastapi import APIRouter, HTTPException

from ..queries import stats, videos

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/{video_id}")
def video_stats(video_id: int) -> dict[str, Any]:
    """Return the three fixed statistics for one video.

    Args:
        video_id: The video to summarize.

    Returns:
        The statistics payload.

    Raises:
        HTTPException: 404, if there is no such video.
    """
    if not videos.exists(video_id):
        raise HTTPException(status_code=404, detail=f"No video with id {video_id}")
    return stats.for_video(video_id)
