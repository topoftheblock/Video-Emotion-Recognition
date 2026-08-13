"""Parses text-based GoEmotions annotations.

Confirmed in the real Bundestag video-emotion CAS: per-sentence text
emotion analysis is represented by a *different* UIMA type than the
per-frame video/audio Emotion parsed in emotion.py --
`org.texttechnologylab.annotation.Emotion` (directly under
`.annotation`, not the `.annotation.emotion` subpackage).

Its per-label scores aren't a nested `scores` feature the way the
video Emotion's are -- they're separate `AnnotationComment` feature
structures (`key`=label, `value`=score as a string) referenced by an
`Emotions` id list on the Emotion FS, e.g.:

    <annotation:Emotion begin="0" end="12" Emotions="1748 1725 ..." model="1724"/>
    <annotation:AnnotationComment xmi:id="1748" reference="1753" key="gratitude" value="0.9999021"/>

This still lands in the same BaseEmotion / EmotionScore tables as
emotion.py, tagged with modality="text", so downstream queries don't
need to know two different emotion pipelines produced the data.
Person linkage isn't available on this type in the source CAS (no
reference back to a speaker/segment), so person_id is left NULL here.
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..typesystem import as_list, get_xmi_id


def _dominant_label_from_comments(comments):
    """Best-effort dominant label: the highest-value AnnotationComment
    (key=label, value=score-as-string). `comments` must already be a
    plain list (see `as_list`)."""
    best_label, best_score = None, None
    for comment in comments:
        raw_score = getattr(comment, "value", None)
        if raw_score is None:
            continue
        try:
            numeric_score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if best_score is None or numeric_score > best_score:
            best_score = numeric_score
            best_label = getattr(comment, "key", None)
    return best_label


def _insert_text_emotion(cursor, entry, emotion_id, video_id, dominant_label):
    """
    Only the columns this annotation type actually carries are listed;
    every other base_emotions column is nullable and defaults to NULL.
    Notably absent: person_id (no speaker reference is encoded on this
    type, see module docstring), the times (it is anchored to character
    offsets, not to the timeline) and the bbox/VAD values (there is no
    frame and no dimensional reading here, only per-label scores).
    """
    cursor.execute(
        """
        INSERT INTO base_emotions (emotion_id, video_id, modality, granularity, begin_offset, end_offset, dominant_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (emotion_id) DO NOTHING
        """,
        (emotion_id, video_id, "text", "sentence", entry.begin, entry.end, dominant_label),
    )


def _insert_text_emotion_scores(cursor, comments, emotion_id):
    """`comments` is a plain list of AnnotationComment FS references
    (see `as_list`), each carrying one GoEmotions label/score pair
    (key/value)."""
    for comment in comments:
        label = getattr(comment, "key", None)
        raw_score = getattr(comment, "value", None)
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None

        cursor.execute(
            """
            INSERT INTO emotion_scores (emotion_id, label, score)
            VALUES (%s, %s, %s)
            ON CONFLICT (emotion_id, label) DO NOTHING
            """,
            (emotion_id, label, score),
        )


def parse(cas, cursor, context):
    video_id = context.get("global_video_id")

    for entry in select_across_views(cas, TYPES["goemotions_emotion"]):
        emotion_id = get_xmi_id(entry)
        comments = as_list(getattr(entry, "Emotions", None))
        dominant_label = _dominant_label_from_comments(comments)
        _insert_text_emotion(cursor, entry, emotion_id, video_id, dominant_label)
        _insert_text_emotion_scores(cursor, comments, emotion_id)
