"""Parses Presence rows from PersonTrack annotations."""

from ..cas_views import select_across_views
from ..config import TYPES
from ..db import get_or_insert_id
from ..identity_resolution import resolve_person_id_via_face_fs
from ..typesystem import get_xmi_id


def _resolve_track_person_id(track, context):
    if hasattr(track, "face") and track.face:
        person_id = resolve_person_id_via_face_fs(track.face, context)
        if person_id is not None:
            return person_id
    if hasattr(track, "person") and track.person:
        return get_xmi_id(track.person)
    return None


def parse(cas, cursor, conn, context):
    video_id = context.get("global_video_id")

    for track in select_across_views(cas, TYPES["person_track"]):
        presence_id = get_xmi_id(track)
        get_or_insert_id(cursor, conn, "Presence", "presence_id", presence_id)
        person_id = _resolve_track_person_id(track, context)

        cursor.execute(
            """
            INSERT INTO Presence (presence_id, person_id, video_id, modality, start_time, end_time, begin, end)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (presence_id) DO NOTHING
            """,
            (
                presence_id,
                person_id,
                video_id,
                getattr(track, "modality", None),
                getattr(track, "timeStart", getattr(track, "start_time", None)),
                getattr(track, "timeEnd", getattr(track, "end_time", None)),
                track.begin,
                track.end,
            ),
        )
