"""Reads segments: shot segments from video, sentences from audio.

Both kinds share the `segments` table and are told apart by `kind`.
"""

from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def _parse_shots(cas: Cas, cursor: Cursor, video_id: int | None) -> None:
    """Insert one segment per camera shot."""
    for shot in select_across_views(cas, TYPES["shot"]):
        segment_id = get_xmi_id(shot)
        cursor.execute(
            """
            INSERT INTO segments
                (segment_id, video_id, kind, seg_index, start_time,
                 end_time, begin_offset, end_offset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, segment_id) DO NOTHING
            """,
            (
                segment_id,
                video_id,
                "shot",
                getattr(shot, "shotIndex", None),
                getattr(shot, "timeStart", None),
                getattr(shot, "timeEnd", None),
                shot.begin,
                shot.end,
            ),
        )


def _resolve_sentence_person_id(sentence: Any) -> int | None:
    """Return the speaker's person id, following the voice reference."""
    if hasattr(sentence, "speakerSegment") and sentence.speakerSegment:
        voice = getattr(sentence.speakerSegment, "voice", None)
        if voice and getattr(voice, "person", None) is not None:
            return get_xmi_id(voice.person)
    return None


def _parse_sentences(cas: Cas, cursor: Cursor, video_id: int | None) -> None:
    """Insert one segment per transcript sentence, with its speaker."""
    for sentence in select_across_views(cas, TYPES["speaker_sentence"]):
        segment_id = get_xmi_id(sentence)
        person_id = _resolve_sentence_person_id(sentence)

        cursor.execute(
            """
            INSERT INTO segments
                (segment_id, video_id, kind, start_time, end_time,
                 begin_offset, end_offset, person_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, segment_id) DO NOTHING
            """,
            (
                segment_id,
                video_id,
                "sentence",
                getattr(sentence, "timeStart", None),
                getattr(sentence, "timeEnd", None),
                sentence.begin,
                sentence.end,
                person_id,
            ),
        )


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's shot and sentence segments.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")
    _parse_shots(cas, cursor, video_id)
    _parse_sentences(cas, cursor, video_id)
