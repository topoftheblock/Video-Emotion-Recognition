"""The video list, and the per-video playback payload."""

from typing import Any

from fastapi import APIRouter, HTTPException

from ..config import VIDEO_DIR
from ..queries import videos

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("")
def list_videos() -> list[dict[str, Any]]:
    """List every imported video, and whether its file is playable.

    The importer places a video in the store under the same filename
    the row carries, but a row can predate that step, if the import ran
    before the video was placed, or outlive it, if the file was deleted
    or never arrived. So presence is checked live rather than assumed:
    this is how the webapp knows which videos it can actually play.

    Returns:
        One entry per video, each with `video_file_available`.
    """
    rows = videos.list_all()
    for video in rows:
        video["video_file_available"] = (VIDEO_DIR / video["filename"]).is_file()
    return rows


@router.get("/{video_id}/data")
def get_video_data(video_id: int) -> dict[str, Any]:
    """Return everything the frontend needs to play one video.

    Args:
        video_id: The video to fetch.

    Returns:
        The playback payload.

    Raises:
        HTTPException: 404, if there is no such video.
    """
    payload = videos.build_playback_payload(video_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No video with id {video_id}")
    return payload
