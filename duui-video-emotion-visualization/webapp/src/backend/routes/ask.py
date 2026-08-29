"""The "Ask" panel: a question, turned into SQL and playable spans."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..query_agent import QueryAgentError, answer_question

router = APIRouter(prefix="/api", tags=["ask"])


class AskRequest(BaseModel):
    """One natural-language question from the panel."""

    question: str


def _playable_segments(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn the agent's rows into spans the frontend can jump to.

    Only a row carrying a video and a start time can be played, so a
    result without those columns yields nothing and the frontend falls
    back to a plain table. Everything else on the row rides along as
    `meta`, which is what the list shows under each timestamp.

    A row with no end time collapses to a zero-length span at its
    start, rather than being dropped: the moment is still worth jumping
    to even when its extent is unknown.

    Args:
        result: The agent's result, with `columns` and `rows`.

    Returns:
        One entry per playable row; empty if none are.
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
def ask_question(payload: AskRequest) -> dict[str, Any]:
    """Answer one question by way of the query agent.

    The agent explores the schema, writes a query, runs it under the
    read-only guard, and chooses which overlays the frontend should
    show for the results.

    Args:
        payload: The question to answer.

    Returns:
        The agent's result, plus the spans the frontend can play.

    Raises:
        HTTPException: 400 if the question is empty, 422 if the agent
            could not answer it.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")
    try:
        result = answer_question(question)
    except QueryAgentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {**result, "segments": _playable_segments(result)}
