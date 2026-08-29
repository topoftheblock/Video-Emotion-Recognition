"""Everything read per video, and the payload assembled from it.

The video row itself, its people, its segments and tokens, its emotions
and its detections.

`build_playback_payload` assembles the single JSON document the
frontend loads once per video and then renders entirely off the
playback time — which is why it is one payload rather than a route per
table.
"""

from typing import Any

from ..db import query

Row = dict[str, Any]


def list_all() -> list[Row]:
    """Return every imported video, newest import first."""
    return query(
        "SELECT video_id, filename, duration, fps, width, height "
        "FROM videos ORDER BY processed_at DESC"
    )


def get(video_id: int) -> Row | None:
    """Return the full video row, or None if there is no such video."""
    rows = query("SELECT * FROM videos WHERE video_id = %s", (video_id,))
    return rows[0] if rows else None


def exists(video_id: int) -> bool:
    """Return whether this video is known — cheaper than `get`."""
    return bool(query("SELECT video_id FROM videos WHERE video_id = %s", (video_id,)))


def get_persons(video_id: int) -> list[Row]:
    """Return the people detected in this video."""
    return query(
        "SELECT person_id, global_person_id, clip_label, "
        "audio_video_match_score, global_person_match_score "
        "FROM persons WHERE video_id = %s",
        (video_id,),
    )


def get_sentences(video_id: int) -> list[Row]:
    """Return this video's sentence segments, in time order."""
    return query(
        "SELECT segment_id, start_time, end_time, person_id "
        "FROM segments WHERE video_id = %s AND kind = 'sentence' ORDER BY start_time",
        (video_id,),
    )


def get_shots(video_id: int) -> list[Row]:
    """Return this video's shot segments, in time order."""
    return query(
        "SELECT segment_id, seg_index, start_time, end_time "
        "FROM segments WHERE video_id = %s AND kind = 'shot' ORDER BY start_time",
        (video_id,),
    )


def get_tokens(video_id: int) -> list[Row]:
    """Return this video's transcript tokens, in time order."""
    return query(
        "SELECT token_id, segment_id, start_time, end_time, word, pos_tag, ner_label "
        "FROM linguistic_tokens WHERE video_id = %s ORDER BY start_time",
        (video_id,),
    )


def get_timeline_emotions(video_id: int) -> list[Row]:
    """Return every emotion reading that sits on the timeline.

    `start_time IS NOT NULL` is not defensive filtering. It is what
    separates two different annotators whose output shares
    `modality='text'`: one produces a reading per sentence carrying real
    times, over a small label set — anger, disgust, fear, joy, neutral,
    sadness, surprise — while the other produces a GoEmotions reading
    over 28 labels, anchored to character offsets with no times at all.

    Both describe the same sentence. Anything treating `modality='text'`
    as a single series therefore counts every sentence twice.

    Everything the frontend renders is driven off the playback time, so
    a reading with no time cannot be placed at all. Leaving those out of
    the payload keeps the trap out of the frontend; they stay reachable
    through `/api/stats` and the query agent.
    """
    return query(
        "SELECT emotion_id, person_id, modality, granularity, start_time, end_time, "
        "frame_index, x, y, w, h, valence, arousal, dominance, dominant_label "
        "FROM base_emotions WHERE video_id = %s AND start_time IS NOT NULL "
        "ORDER BY start_time",
        (video_id,),
    )


def get_emotion_scores(video_id: int, emotion_ids: list[int]) -> list[Row]:
    """Return the per-label scores for these emotions, highest first.

    Scoped to one video, and not to the ids alone: `emotion_id` comes
    from the CAS's own per-document counter, so the same id exists in
    other videos too — see the identity note in
    `pgvector-db/schema.sql`. Without the video, this would pull in
    other videos' scores for the same numbers and pile several
    readings' worth of labels onto one reading.

    Args:
        video_id: The video the emotions belong to.
        emotion_ids: The emotions to fetch scores for.

    Returns:
        One row per label per emotion; empty if no ids were given.
    """
    if not emotion_ids:
        return []
    return query(
        "SELECT emotion_id, label, score FROM emotion_scores "
        "WHERE video_id = %s AND emotion_id = ANY(%s) ORDER BY score DESC",
        (video_id, emotion_ids),
    )


def _get_detections(table: str, video_id: int) -> list[Row]:
    """Return one table's detections for this video, in time order.

    `table` is interpolated into the statement rather than passed as a
    parameter, which a table name cannot be. Both call sites below pass
    a literal, so no external value reaches it.
    """
    return query(
        "SELECT detection_id, presence_id, person_id, frame_index, t_time, "
        f"x, y, w, h, detection_score FROM {table} "
        "WHERE video_id = %s ORDER BY t_time",
        (video_id,),
    )


def get_face_detections(video_id: int) -> list[Row]:
    """Return this video's face detections, in time order."""
    return _get_detections("face_detections", video_id)


def get_person_detections(video_id: int) -> list[Row]:
    """Return this video's person detections, in time order."""
    return _get_detections("person_detections", video_id)


def assemble_sentence_text(sentence: Row, tokens: list[Row]) -> str:
    """Join the tokens that fall inside one sentence, in time order.

    Matched by time overlap rather than by `linguistic_tokens.
    segment_id`. That column is not reliably populated on the source
    annotation — in the data this was checked against it is never
    populated — so the time range is the only link that actually works.

    Args:
        sentence: The sentence segment, with its start and end times.
        tokens: This video's tokens, in time order.

    Returns:
        The sentence text, or "" when the sentence has no time span.
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


def build_playback_payload(video_id: int) -> dict[str, Any] | None:
    """Assemble everything the frontend needs to play one video.

    Args:
        video_id: The video to build the payload for.

    Returns:
        The payload, or None if there is no such video.
    """
    video = get(video_id)
    if video is None:
        return None

    sentences = get_sentences(video_id)
    tokens = get_tokens(video_id)
    for sentence in sentences:
        sentence["text"] = assemble_sentence_text(sentence, tokens)

    emotions = get_timeline_emotions(video_id)
    emotions_by_modality: dict[str, list[Row]] = {"video": [], "audio": [], "text": []}
    for emotion in emotions:
        emotions_by_modality.setdefault(emotion["modality"] or "video", []).append(
            emotion
        )

    scores_by_emotion: dict[int, list[Row]] = {}
    for score in get_emotion_scores(video_id, [e["emotion_id"] for e in emotions]):
        scores_by_emotion.setdefault(score["emotion_id"], []).append(
            {"label": score["label"], "score": score["score"]}
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
