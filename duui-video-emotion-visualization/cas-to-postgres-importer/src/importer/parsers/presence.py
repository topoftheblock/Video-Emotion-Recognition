"""Reads presences: the spans during which a person is present.

The `presences` table covers two modalities. `visible` means on screen,
and comes from PersonTrack; `speech` means speaking, and comes from
SpeakerSegment. PersonTrack has no `modality` feature in the real
typesystem, so `visible` is set here rather than read from the CAS.
"""

from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.person_resolution import (
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def _resolve_track_person_id(track: Any, context: dict) -> int | None:
    """Return the tracked person's id, by face reference or directly."""
    if hasattr(track, "face") and track.face:
        person_id = resolve_person_id_via_face_fs(track.face, context)
        if person_id is not None:
            return person_id
    if hasattr(track, "person") and track.person:
        return get_xmi_id(track.person)
    return None


def _parse_visible_presences(
    cas: Cas, cursor: Cursor, video_id: int | None, context: dict
) -> None:
    """Insert one presence per on-screen track."""
    for track in select_across_views(cas, TYPES["person_track"]):
        presence_id = get_xmi_id(track)
        person_id = _resolve_track_person_id(track, context)

        cursor.execute(
            """
            INSERT INTO presences
                (presence_id, person_id, video_id, modality, start_time,
                 end_time, begin_offset, end_offset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, presence_id) DO NOTHING
            """,
            (
                presence_id,
                person_id,
                video_id,
                "visible",
                getattr(track, "timeStart", getattr(track, "start_time", None)),
                getattr(track, "timeEnd", getattr(track, "end_time", None)),
                # These tracks span frames, not text: no offsets.
                None,
                None,
            ),
        )


def _parse_speech_presences(
    cas: Cas, cursor: Cursor, video_id: int | None, context: dict
) -> None:
    """Insert one presence per span of speech."""
    for segment in select_across_views(cas, TYPES["speaker_segment"]):
        presence_id = get_xmi_id(segment)
        voice = getattr(segment, "voice", None)
        person_id = resolve_person_id_via_voice_fs(voice, context)

        cursor.execute(
            """
            INSERT INTO presences
                (presence_id, person_id, video_id, modality, start_time,
                 end_time, begin_offset, end_offset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, presence_id) DO NOTHING
            """,
            (
                presence_id,
                person_id,
                video_id,
                "speech",
                getattr(segment, "timeStart", None),
                getattr(segment, "timeEnd", None),
                segment.begin,
                segment.end,
            ),
        )


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's visible and speech presences.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")
    _parse_visible_presences(cas, cursor, video_id, context)
    _parse_speech_presences(cas, cursor, video_id, context)
