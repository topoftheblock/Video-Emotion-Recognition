"""The video list and the per-video playback payload."""

from fastapi import APIRouter, HTTPException

from ..config import VIDEO_DIR
from ..queries import videos

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("")
def list_videos():
    """
    Every imported video, plus whether its file actually exists in
    VIDEO_DIR right now -- this is how the webapp "knows" which videos
    it can play: the importer places the file there under the same
    `filename` (see
    cas-to-postgres-importer/src/importer/media.py), but a DB row
    can still predate that step (import ran before the video was
    placed) or outlive it (the file was deleted/never arrived), so this
    is checked live rather than assumed.
    """
    rows = videos.list_all()
    for video in rows:
        video["video_file_available"] = (VIDEO_DIR / video["filename"]).is_file()
    return rows


@router.get("/{video_id}/data")
def get_video_data(video_id: int):
    payload = videos.build_playback_payload(video_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No video with id {video_id}")
    return payload
