"""
Everything read per video: the video row itself, its persons, its
segments/tokens, its emotions and its detections.

`build_playback_payload` assembles the single JSON blob the frontend
loads once per video and then renders entirely off `currentTime` --
which is why it is one payload rather than a route per table.
"""

from ..db import query


def list_all():
    """Every imported video, newest import first."""
    return query(
        "SELECT video_id, filename, duration, fps, width, height FROM videos ORDER BY processed_at DESC"
    )


def get(video_id):
    """The full videos row, or None if there is no such video."""
    rows = query("SELECT * FROM videos WHERE video_id = %s", (video_id,))
    return rows[0] if rows else None


def exists(video_id):
    """True if `video_id` is a known video -- cheaper than get()."""
    return bool(query("SELECT video_id FROM videos WHERE video_id = %s", (video_id,)))


def get_persons(video_id):
    return query(
        "SELECT person_id, global_person_id, clip_label, match_score "
        "FROM persons WHERE video_id = %s",
        (video_id,),
    )


def get_sentences(video_id):
    return query(
        "SELECT segment_id, start_time, end_time, person_id "
        "FROM segments WHERE video_id = %s AND kind = 'sentence' ORDER BY start_time",
        (video_id,),
    )


def get_shots(video_id):
    return query(
        "SELECT segment_id, seg_index, start_time, end_time "
        "FROM segments WHERE video_id = %s AND kind = 'shot' ORDER BY start_time",
        (video_id,),
    )


def get_tokens(video_id):
    return query(
        "SELECT token_id, segment_id, start_time, end_time, word, pos_tag, ner_label "
        "FROM linguistic_tokens WHERE video_id = %s ORDER BY start_time",
        (video_id,),
    )


def get_emotions(video_id):
    return query(
        "SELECT emotion_id, person_id, modality, granularity, start_time, end_time, "
        "frame_index, x, y, w, h, valence, arousal, dominance, dominant_label "
        "FROM base_emotions WHERE video_id = %s ORDER BY start_time",
        (video_id,),
    )


def get_emotion_scores(emotion_ids):
    """Per-label scores for the given emotions, highest score first."""
    if not emotion_ids:
        return []
    return query(
        "SELECT emotion_id, label, score FROM emotion_scores "
        "WHERE emotion_id = ANY(%s) ORDER BY score DESC",
        (emotion_ids,),
    )


def _get_detections(table, video_id):
    return query(
        f"SELECT detection_id, presence_id, person_id, frame_index, t_time, x, y, w, h, detection_score "
        f"FROM {table} WHERE video_id = %s ORDER BY t_time",
        (video_id,),
    )


def get_face_detections(video_id):
    return _get_detections("face_detections", video_id)


def get_person_detections(video_id):
    return _get_detections("person_detections", video_id)


def assemble_sentence_text(sentence, tokens):
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


def build_playback_payload(video_id):
    """
    The whole per-video payload the frontend renders from, or None if
    there is no such video.
    """
    video = get(video_id)
    if video is None:
        return None

    sentences = get_sentences(video_id)
    tokens = get_tokens(video_id)
    for sentence in sentences:
        sentence["text"] = assemble_sentence_text(sentence, tokens)

    emotions = get_emotions(video_id)
    emotions_by_modality = {"video": [], "audio": [], "text": []}
    for e in emotions:
        emotions_by_modality.setdefault(e["modality"] or "video", []).append(e)

    scores_by_emotion = {}
    for s in get_emotion_scores([e["emotion_id"] for e in emotions]):
        scores_by_emotion.setdefault(s["emotion_id"], []).append(
            {"label": s["label"], "score": s["score"]}
        )

    return {
        "video": video,
        "persons": get_persons(video_id),
        "sentences": sentences,
        "shots": get_shots(video_id),
        "emotions": emotions_by_modality,
        "emotion_scores": scores_by_emotion,
        "detections": {
            "face": get_face_detections(video_id),
            "person": get_person_detections(video_id),
        },
    }
