"""Reads text emotions, which arrive in a shape of their own.

Per-sentence text emotion analysis uses a *different* UIMA type from
the per-frame video and audio Emotion that `emotion.py` reads:
`org.texttechnologylab.annotation.Emotion`, directly under
`.annotation` rather than in the `.annotation.emotion` subpackage.

Its per-label scores are not a nested feature the way the video
Emotion's are. They are separate AnnotationComment structures, with the
label in `key` and the score in `value` as a string, referenced by an
`Emotions` id list on the Emotion:

    <annotation:Emotion begin="0" end="12" Emotions="1748 1725 ..."/>
    <annotation:AnnotationComment xmi:id="1748" key="gratitude"
                                  value="0.9999021"/>

These still land in the same two tables, tagged `modality="text"`, so a
query does not need to know that two different pipelines produced the
data. No speaker or segment reference is encoded on this type, so
`person_id` is left NULL.
"""

from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.types import TYPES
from ..cas.typesystem import as_list, get_xmi_id
from ..cas.views import select_across_views


def _dominant_label_from_comments(comments: list) -> str | None:
    """Recover a dominant label from the highest-valued comment.

    Args:
        comments: The AnnotationComment structures, already a plain
            list; see `as_list`.

    Returns:
        The highest-scoring label, or None if none has a usable score.
    """
    best_label, best_score = None, None
    for comment in comments:
        raw_score = getattr(comment, "value", None)
        if raw_score is None:
            continue
        try:
            numeric_score = float(raw_score)
        except TypeError, ValueError:
            continue
        if best_score is None or numeric_score > best_score:
            best_score = numeric_score
            best_label = getattr(comment, "key", None)
    return best_label


def _insert_text_emotion(
    cursor: Cursor,
    entry: Any,
    emotion_id: int | None,
    video_id: int | None,
    dominant_label: str | None,
) -> None:
    """Insert one text emotion row.

    Only the columns this annotation type carries are listed; every
    other column is nullable and defaults to NULL. Absent by nature:
    `person_id`, since no speaker reference is encoded on this type;
    the times, since it is anchored to character offsets rather than to
    the timeline; and the box and valence-arousal-dominance values,
    since there is no frame and no dimensional reading here, only
    per-label scores.
    """
    cursor.execute(
        """
        INSERT INTO base_emotions
            (emotion_id, video_id, modality, granularity, begin_offset,
             end_offset, dominant_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (video_id, emotion_id) DO NOTHING
        """,
        (
            emotion_id,
            video_id,
            "text",
            "sentence",
            entry.begin,
            entry.end,
            dominant_label,
        ),
    )


def _insert_text_emotion_scores(
    cursor: Cursor, comments: list, emotion_id: int | None, video_id: int | None
) -> None:
    """Insert the label distribution carried by the comments.

    Args:
        cursor: An open cursor, inside the import's transaction.
        comments: AnnotationComment structures, each holding one label
            in `key` and its score in `value`.
        emotion_id: The base emotion these scores belong to.
        video_id: The video being imported.
    """
    for comment in comments:
        label = getattr(comment, "key", None)
        raw_score = getattr(comment, "value", None)
        try:
            score = float(raw_score) if raw_score is not None else None
        except TypeError, ValueError:
            score = None

        cursor.execute(
            """
            INSERT INTO emotion_scores (video_id, emotion_id, label, score)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (video_id, emotion_id, label) DO NOTHING
            """,
            (video_id, emotion_id, label, score),
        )


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's text emotions and their scores.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")

    for entry in select_across_views(cas, TYPES["goemotions_emotion"]):
        emotion_id = get_xmi_id(entry)
        comments = as_list(getattr(entry, "Emotions", None))
        dominant_label = _dominant_label_from_comments(comments)
        _insert_text_emotion(cursor, entry, emotion_id, video_id, dominant_label)
        _insert_text_emotion_scores(cursor, comments, emotion_id, video_id)
