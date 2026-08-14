"""The natural-language "Ask" panel: question -> SQL -> playable segments."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..query_agent import QueryAgentError, answer_question

router = APIRouter(prefix="/api", tags=["ask"])


class AskRequest(BaseModel):
    question: str


def _playable_segments(result):
    """
    Turn agent result rows into clips the frontend can jump to.

    Only rows carrying video_id + start_time + end_time can be played,
    so a result without those columns yields no segments at all and the
    frontend falls back to rendering a plain table. Everything else on
    the row rides along as `meta`, which is what the segment list shows
    underneath each timestamp.
    """
    if not {"video_id", "start_time", "end_time"} <= set(result["columns"]):
        return []

    segments = []
    for row in result["rows"]:
        if row.get("video_id") is None or row.get("start_time") is None:
            continue
        meta = {
            k: v
            for k, v in row.items()
            if k not in ("video_id", "start_time", "end_time")
        }
        segments.append(
            {
                "video_id": row["video_id"],
                "start_time": row["start_time"],
                "end_time": row.get("end_time") or row["start_time"],
                "meta": meta,
            }
        )
    return segments


@router.post("/ask")
def ask_question(payload: AskRequest):
    """
    Natural-language question -> SQL agent. Runs the question through
    the LLM-backed NL->SQL agent (backend.query_agent), which explores
    the schema, writes a query, and picks which display overlays
    (transcript/bounding boxes/emotion modalities) the frontend should
    show for the results.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")
    try:
        result = answer_question(question)
    except QueryAgentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {**result, "segments": _playable_segments(result)}
