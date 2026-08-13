"""Parses Presence rows.

The `presences` table covers two distinct modalities (per the
canonical schema doc): `'visible'` (a face/body being on screen,
sourced from PersonTrack) and `'speech'` (a person talking, sourced
from SpeakerSegment). PersonTrack itself has no `modality` feature in
the real typesystem, so `'visible'` is set explicitly here rather than
read from the CAS.
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..identity_resolution import (
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from ..typesystem import get_xmi_id


def _resolve_track_person_id(track, context):
    if hasattr(track, "face") and track.face:
        person_id = resolve_person_id_via_face_fs(track.face, context)
        if person_id is not None:
            return person_id
    if hasattr(track, "person") and track.person:
        return get_xmi_id(track.person)
    return None


def _parse_visible_presences(cas, cursor, video_id, context):
    for track in select_across_views(cas, TYPES["person_track"]):
        presence_id = get_xmi_id(track)
        person_id = _resolve_track_person_id(track, context)

        cursor.execute(
            """
            INSERT INTO presences (presence_id, person_id, video_id, modality, start_time, end_time, begin_offset, end_offset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (presence_id) DO NOTHING
            """,
            (
                presence_id,
                person_id,
                video_id,
                "visible",
                getattr(track, "timeStart", getattr(track, "start_time", None)),
                getattr(track, "timeEnd", getattr(track, "end_time", None)),
                # Face/body tracks span frames, not text -- no offsets.
                None,
                None,
            ),
        )


def _parse_speech_presences(cas, cursor, video_id, context):
    for segment in select_across_views(cas, TYPES["speaker_segment"]):
        presence_id = get_xmi_id(segment)
        voice = getattr(segment, "voice", None)
        person_id = resolve_person_id_via_voice_fs(voice, context)

        cursor.execute(
            """
            INSERT INTO presences (presence_id, person_id, video_id, modality, start_time, end_time, begin_offset, end_offset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (presence_id) DO NOTHING
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


def parse(cas, cursor, context):
    video_id = context.get("global_video_id")
    _parse_visible_presences(cas, cursor, video_id, context)
    _parse_speech_presences(cas, cursor, video_id, context)
