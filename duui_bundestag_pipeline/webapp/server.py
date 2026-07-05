"""
Web viewer backend for the DUUI Bundestag pipeline.

Serves two things:
  1. The video file itself, from VIDEO_DIR (range-request aware, so
     seeking works) -- see .env's DUUI_VIDEO_DIR.
  2. A single JSON payload per video with everything the frontend
     needs to render subtitles, emotions, and bounding boxes in sync
     with video playback time: sentences (with assembled subtitle
     text), per-modality emotions, and face/person detections.

Run from the project root:
    uvicorn webapp.server:app --reload
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import RealDictCursor

from duui_parser.config import DB_CONFIG
from duui_parser.db import get_db_connection

VIDEO_DIR = Path(os.environ.get("DUUI_VIDEO_DIR", "cas")).resolve()
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="DUUI Bundestag Video Viewer")


def _query(sql, params=None):
    """Run one query and return a list of plain dict rows."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _assemble_sentence_text(sentence, tokens):
    """
    Join every token whose start_time falls inside this sentence's
    [start_time, end_time] window, in time order. Matched by time
    overlap rather than linguistic_tokens.segment_id -- confirmed
    against a real CAS that segment_id isn't always populated on the
    source annotation, so time-range matching is the reliable path.
    """
    start, end = sentence["start_time"], sentence["end_time"]
    if start is None or end is None:
        return ""
    words = [
        t["word"]
        for t in tokens
        if t["start_time"] is not None and start <= t["start_time"] <= end
    ]
    return " ".join(w for w in words if w)


@app.get("/api/videos")
def list_videos():
    return _query(
        "SELECT video_id, filename, duration, fps, width, height FROM videos ORDER BY video_id"
    )


@app.get("/api/videos/{video_id}/data")
def get_video_data(video_id: int):
    video_rows = _query("SELECT * FROM videos WHERE video_id = %s", (video_id,))
    if not video_rows:
        raise HTTPException(status_code=404, detail=f"No video with id {video_id}")
    video = video_rows[0]

    persons = _query(
        "SELECT person_id, global_person_id, clip_label, match_score "
        "FROM persons WHERE video_id = %s",
        (video_id,),
    )

    sentences = _query(
        "SELECT segment_id, start_time, end_time, person_id "
        "FROM segments WHERE video_id = %s AND kind = 'sentence' ORDER BY start_time",
        (video_id,),
    )
    shots = _query(
        "SELECT segment_id, seg_index, start_time, end_time "
        "FROM segments WHERE video_id = %s AND kind = 'shot' ORDER BY start_time",
        (video_id,),
    )
    tokens = _query(
        "SELECT token_id, segment_id, start_time, end_time, word, pos_tag, ner_label "
        "FROM linguistic_tokens WHERE video_id = %s ORDER BY start_time",
        (video_id,),
    )
    for sentence in sentences:
        sentence["text"] = _assemble_sentence_text(sentence, tokens)

    emotions = _query(
        "SELECT emotion_id, person_id, modality, granularity, start_time, end_time, "
        "frame_index, x, y, w, h, valence, arousal, dominance, dominant_label "
        "FROM base_emotions WHERE video_id = %s ORDER BY start_time",
        (video_id,),
    )
    emotions_by_modality = {"video": [], "audio": [], "text": []}
    for e in emotions:
        emotions_by_modality.setdefault(e["modality"] or "video", []).append(e)

    emotion_ids = [e["emotion_id"] for e in emotions]
    scores_by_emotion = {}
    if emotion_ids:
        scores = _query(
            "SELECT emotion_id, label, score FROM emotion_scores "
            "WHERE emotion_id = ANY(%s) ORDER BY score DESC",
            (emotion_ids,),
        )
        for s in scores:
            scores_by_emotion.setdefault(s["emotion_id"], []).append(
                {"label": s["label"], "score": s["score"]}
            )

    face_detections = _query(
        "SELECT detection_id, presence_id, person_id, frame_index, t_time, x, y, w, h, detection_score "
        "FROM face_detections WHERE video_id = %s ORDER BY t_time",
        (video_id,),
    )
    person_detections = _query(
        "SELECT detection_id, presence_id, person_id, frame_index, t_time, x, y, w, h, detection_score "
        "FROM person_detections WHERE video_id = %s ORDER BY t_time",
        (video_id,),
    )

    return {
        "video": video,
        "persons": persons,
        "sentences": sentences,
        "shots": shots,
        "emotions": emotions_by_modality,
        "emotion_scores": scores_by_emotion,
        "detections": {"face": face_detections, "person": person_detections},
    }


app.mount("/media", StaticFiles(directory=VIDEO_DIR), name="media")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
