"""Reads video and audio emotions into two related tables.

`base_emotions` takes one row per Emotion annotation, and
`emotion_scores` the per-label scores nested inside it.

Some pipelines set `.personId` on the Emotion directly. The real CAS
does not: the Emotion carries a `.reference` to the detection it was
computed from, which links on to a track and from there to an identity.
`_resolve_emotion_person_id` tries the direct attribute first and walks
that chain otherwise.
"""

from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.person_resolution import (
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from ..cas.types import TYPES
from ..cas.typesystem import as_list, get_xmi_id
from ..cas.views import select_across_views


def _resolve_emotion_person_id(emotion: Any, context: dict) -> int | None:
    """Return the person this emotion belongs to.

    `.personId` is used directly when present. Otherwise `.reference`
    is walked according to what it points at: a video detection,
    through `reference.track.face`, or a speaker sentence, through
    `reference.speakerSegment.voice`. Both are confirmed in the real
    CAS, one per modality.

    Args:
        emotion: The Emotion structure.
        context: The shared context, holding the person lookup maps.

    Returns:
        The person's id, or None if no path resolves one.
    """
    person_id = getattr(emotion, "personId", None)
    if person_id is not None:
        return person_id

    reference = getattr(emotion, "reference", None)
    if reference is None:
        return None

    track = getattr(reference, "track", None)
    if track is not None:
        face = getattr(track, "face", None)
        person_id = resolve_person_id_via_face_fs(face, context)
        if person_id is not None:
            return person_id

    speaker_segment = getattr(reference, "speakerSegment", None)
    if speaker_segment is not None:
        voice = getattr(speaker_segment, "voice", None)
        person_id = resolve_person_id_via_voice_fs(voice, context)
        if person_id is not None:
            return person_id

    return None


def _dominant_label_from_scores(scores: list) -> str | None:
    """Recover a dominant label by taking the highest-scoring one.

    Used when the CAS does not set one directly, which is the case on
    the real per-frame Emotion instances.

    Args:
        scores: The nested scores, already a plain list. An FSArray
            wrapper would iterate incorrectly; see `as_list`.

    Returns:
        The highest-scoring label, or None if none has a usable score.
    """
    best_label, best_score = None, None
    for score in scores:
        raw_score = getattr(score, "score", None)
        if raw_score is None:
            continue
        try:
            numeric_score = float(raw_score)
        except TypeError, ValueError:
            continue
        if best_score is None or numeric_score > best_score:
            best_score = numeric_score
            best_label = getattr(score, "label", None)
    return best_label


def _insert_base_emotion(
    cursor: Cursor,
    emotion: Any,
    emotion_id: int | None,
    person_id: int | None,
    video_id: int | None,
    scores: list,
) -> None:
    """Insert or update one base emotion row.

    DO UPDATE rather than DO NOTHING, deliberately: `emotion_id` comes
    from the CAS's own `xmi:id` space, so re-importing the same file
    must overwrite the row with the re-parsed values instead of keeping
    whatever was written first.
    """
    cursor.execute(
        """
        INSERT INTO base_emotions
            (emotion_id, person_id, video_id, modality, granularity,
             start_time, end_time, begin_offset, end_offset, frame_index,
             x, y, w, h, valence, arousal, dominance, dominant_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s)
        ON CONFLICT (video_id, emotion_id) DO UPDATE SET
            person_id = EXCLUDED.person_id, video_id = EXCLUDED.video_id,
            modality = EXCLUDED.modality, granularity = EXCLUDED.granularity,
            start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time,
            begin_offset = EXCLUDED.begin_offset, end_offset = EXCLUDED.end_offset,
            frame_index = EXCLUDED.frame_index, x = EXCLUDED.x, y = EXCLUDED.y,
            w = EXCLUDED.w, h = EXCLUDED.h, valence = EXCLUDED.valence,
            arousal = EXCLUDED.arousal, dominance = EXCLUDED.dominance,
            dominant_label = EXCLUDED.dominant_label
        """,
        (
            emotion_id,
            person_id,
            video_id,
            getattr(emotion, "modality", None),
            getattr(emotion, "granularity", None),
            getattr(emotion, "timeStart", None),
            getattr(emotion, "timeEnd", None),
            emotion.begin,
            emotion.end,
            getattr(emotion, "frameIndex", None),
            getattr(emotion, "x", None),
            getattr(emotion, "y", None),
            getattr(emotion, "width", None),
            getattr(emotion, "height", None),
            getattr(emotion, "valence", None),
            getattr(emotion, "arousal", None),
            getattr(emotion, "dominance", None),
            getattr(emotion, "dominant_label", None)
            or _dominant_label_from_scores(scores),
        ),
    )


def _insert_emotion_scores(
    cursor: Cursor, scores: list, emotion_id: int | None, video_id: int | None
) -> None:
    """Insert the full label distribution for one base emotion."""
    for score in scores:
        cursor.execute(
            """
            INSERT INTO emotion_scores (video_id, emotion_id, label, score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (video_id, emotion_id, label) DO NOTHING
            """,
            (
                video_id,
                emotion_id,
                getattr(score, "label", None),
                getattr(score, "score", None),
            ),
        )


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's emotions and their score distributions.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")

    for emotion in select_across_views(cas, TYPES["emotion"]):
        emotion_id = get_xmi_id(emotion)
        person_id = _resolve_emotion_person_id(emotion, context)
        scores = as_list(getattr(emotion, "scores", None))

        _insert_base_emotion(cursor, emotion, emotion_id, person_id, video_id, scores)
        _insert_emotion_scores(cursor, scores, emotion_id, video_id)
