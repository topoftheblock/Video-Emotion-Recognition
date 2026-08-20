"""Fixed emotion statistics for one video."""

from fastapi import APIRouter, HTTPException

from ..queries import stats, videos

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/{video_id}")
def video_stats(video_id: int):
    if not videos.exists(video_id):
        raise HTTPException(status_code=404, detail=f"No video with id {video_id}")
    return stats.for_video(video_id)
