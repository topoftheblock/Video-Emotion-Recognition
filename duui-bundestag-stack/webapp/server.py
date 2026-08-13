"""
Web viewer backend for the DUUI Bundestag pipeline.

Serves two things:
  1. The video file itself, from VIDEO_DIR (range-request aware, so
     seeking works) -- see .env's DUUI_VIDEO_DIR.
  2. A single JSON payload per video with everything the frontend
     needs to render subtitles, emotions, and bounding boxes in sync
     with video playback time: sentences (with assembled subtitle
     text), per-modality emotions, and face/person detections.

Run from this directory (webapp/ is self-contained -- it has no code
outside itself):
    uvicorn server:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

from duui_webapp.config import VIDEO_MEDIA_DIR
from duui_webapp.db import get_db_connection
from duui_webapp.query_agent import QueryAgentError, answer_question

# Same DUUI_VIDEO_DIR the importer writes into
# (importer/duui_parser/media.py) -- this is the single place both
# sides agree a video for `videos.filename = X` lives at
# `<VIDEO_DIR>/X`. See duui_webapp/config.py's VIDEO_MEDIA_DIR comment
# and README "Docker architecture".
VIDEO_DIR = Path(VIDEO_MEDIA_DIR).resolve()
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="DUUI Bundestag Video Viewer")


@app.get("/healthz")
def healthz():
    """
    Liveness + DB-connectivity check for orchestrators/`docker compose
    healthcheck` -- deliberately does a real query, not just "the
    process is up", since a webapp that's running but can't reach
    Postgres is not actually healthy from a caller's perspective.
    """
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}") from exc
    return {"status": "ok"}


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
    """
    Every imported video, plus whether its file actually exists in
    VIDEO_DIR right now -- this is how the webapp "knows" which videos
    it can play: the importer places the file there under the same
    `filename` (see importer/duui_parser/media.py), but a DB row can still
    predate that step (import ran before the video was placed) or
    outlive it (the file was deleted/never arrived), so this is
    checked live rather than assumed.
    """
    videos = _query(
        "SELECT video_id, filename, duration, fps, width, height FROM videos ORDER BY processed_at DESC"
    )
    for video in videos:
        video["video_file_available"] = (VIDEO_DIR / video["filename"]).is_file()
    return videos


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

    fused_emotions = _query(
        "SELECT fused_id, person_id, fusion_method, target_modality, "
        "start_time, end_time, valence, arousal, dominant_label "
        "FROM fused_emotions WHERE video_id = %s ORDER BY start_time",
        (video_id,),
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
        "fused_emotions": fused_emotions,
        "detections": {"face": face_detections, "person": person_detections},
    }


@app.get("/api/persons/global")
def list_global_persons():
    """
    Cross-video person identity: every global_persons cluster that
    importer/duui_parser/parsers/global_identity.py has linked two or more
    video-local `persons` rows into, with which video/clip_label each
    member came from. A person with no cross-video match (still the
    common case -- see global_identity.py's docstring) simply doesn't
    appear here; this endpoint is specifically "who spans videos", not
    "everyone".
    """
    rows = _query(
        """
        SELECT gp.global_person_id, gp.real_name,
               p.person_id, p.video_id, p.clip_label, p.match_score,
               v.filename AS video_filename
        FROM global_persons gp
        JOIN persons p ON p.global_person_id = gp.global_person_id
        JOIN videos v ON v.video_id = p.video_id
        ORDER BY gp.global_person_id, v.processed_at
        """
    )
    clusters = {}
    for row in rows:
        cluster = clusters.setdefault(
            row["global_person_id"],
            {"global_person_id": row["global_person_id"], "real_name": row["real_name"], "members": []},
        )
        cluster["members"].append(
            {
                "person_id": row["person_id"],
                "video_id": row["video_id"],
                "video_filename": row["video_filename"],
                "clip_label": row["clip_label"],
                "match_score": row["match_score"],
            }
        )
    return list(clusters.values())


def _emotion_distribution(video_id):
    """Stat 1: how often each dominant_label occurred, per modality."""
    return _query(
        """
        SELECT modality, dominant_label, count(*) AS n
        FROM base_emotions
        WHERE video_id = %s AND dominant_label IS NOT NULL
        GROUP BY modality, dominant_label
        ORDER BY modality, n DESC
        """,
        (video_id,),
    )


def _person_emotion_averages(video_id):
    """Stat 2: mean valence/arousal per person, per modality."""
    return _query(
        """
        SELECT be.person_id, COALESCE(p.clip_label, 'person ' || be.person_id::text) AS clip_label,
               be.modality, avg(be.valence) AS avg_valence, avg(be.arousal) AS avg_arousal, count(*) AS n
        FROM base_emotions be
        LEFT JOIN persons p ON p.person_id = be.person_id
        WHERE be.video_id = %s AND be.person_id IS NOT NULL AND be.valence IS NOT NULL
        GROUP BY be.person_id, p.clip_label, be.modality
        ORDER BY be.person_id, be.modality
        """,
        (video_id,),
    )


def _modality_agreement(video_id):
    """
    Stat 3: of the sentences with both a text and a video emotion
    reading, what fraction agree on valence sign (both positive or
    both negative)? A single summary number, not per-sentence rows --
    see schema_context.py's "Cross-modality label comparison" note for
    why this uses valence sign rather than comparing dominant_label
    strings across modalities directly.
    """
    rows = _query(
        """
        WITH text_anchored AS (
            SELECT s.segment_id, s.start_time, s.end_time, s.person_id, te.valence AS text_valence
            FROM segments s
            JOIN base_emotions te
              ON te.video_id = s.video_id AND te.modality = 'text'
             AND te.begin_offset >= s.begin_offset AND te.end_offset <= s.end_offset
            WHERE s.kind = 'sentence' AND s.video_id = %s AND te.valence IS NOT NULL
        ),
        video_per_sentence AS (
            SELECT ta.segment_id, avg(ve.valence) AS video_valence
            FROM text_anchored ta
            JOIN base_emotions ve
              ON ve.video_id = %s AND ve.modality = 'video' AND ve.person_id = ta.person_id
             AND ve.start_time BETWEEN ta.start_time AND ta.end_time AND ve.valence IS NOT NULL
            GROUP BY ta.segment_id
        )
        SELECT count(*) AS n_compared,
               count(*) FILTER (WHERE sign(ta.text_valence) = sign(vp.video_valence)) AS n_agree
        FROM text_anchored ta
        JOIN video_per_sentence vp ON vp.segment_id = ta.segment_id
        """,
        (video_id, video_id),
    )
    n_compared = rows[0]["n_compared"] if rows else 0
    n_agree = rows[0]["n_agree"] if rows else 0
    return {
        "n_compared": n_compared,
        "n_agree": n_agree,
        "agreement_pct": round(100 * n_agree / n_compared, 1) if n_compared else None,
    }


@app.get("/api/stats/{video_id}")
def video_stats(video_id: int):
    """
    A handful of fixed (not LLM-written) emotion statistics for one
    video -- deliberately plain SQL rather than routed through the
    NL->SQL agent, both for speed/determinism and so there's always at
    least a few analyses available even with the query agent
    unconfigured. Computed on demand, not cached/written back to the
    DB -- see README "Emotion statistics" for why.
    """
    video_rows = _query("SELECT video_id FROM videos WHERE video_id = %s", (video_id,))
    if not video_rows:
        raise HTTPException(status_code=404, detail=f"No video with id {video_id}")

    return {
        "emotion_distribution": _emotion_distribution(video_id),
        "person_averages": _person_emotion_averages(video_id),
        "modality_agreement": _modality_agreement(video_id),
    }


class AskRequest(BaseModel):
    question: str


@app.post("/api/ask")
def ask_question(payload: AskRequest):
    """
    Natural-language question -> SQL agent. Runs the question through
    the LLM-backed NL->SQL agent (duui_webapp.query_agent), which
    explores the schema, writes a query, and picks which display
    overlays (transcript/bounding boxes/emotion modalities) the
    frontend should show for the results.
    """
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")
    try:
        result = answer_question(question)
    except QueryAgentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    has_playable_columns = {"video_id", "start_time", "end_time"} <= set(result["columns"])
    segments = []
    if has_playable_columns:
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

    return {**result, "segments": segments}


app.mount("/media", StaticFiles(directory=VIDEO_DIR), name="media")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
