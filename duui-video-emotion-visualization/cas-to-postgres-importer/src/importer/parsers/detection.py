"""Reads detections: one bounding box per person per frame.

Face detections and person detections — the face box and the body box —
share a shape: presence, person, frame, box and score. One helper
therefore fills both tables.
"""

from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.person_resolution import resolve_person_id_via_face_fs
from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def _resolve_detection_person_id(detection: Any, context: dict) -> int | None:
    """Return the detected person's id, through the track's face."""
    track = getattr(detection, "track", None)
    if track and getattr(track, "face", None):
        return resolve_person_id_via_face_fs(track.face, context)
    return None


def _parse_detections(
    cas: Cas,
    cursor: Cursor,
    uima_type: str,
    table_name: str,
    video_id: int | None,
    context: dict,
) -> None:
    """Insert every detection of one UIMA type into one table.

    `table_name` is interpolated into the statement rather than passed
    as a parameter, which a table name cannot be. Both call sites below
    pass a literal, so no external value reaches it.
    """
    for detection in select_across_views(cas, uima_type):
        detection_id = get_xmi_id(detection)
        presence_id = get_xmi_id(getattr(detection, "track", None))
        person_id = _resolve_detection_person_id(detection, context)

        cursor.execute(
            f"""
            INSERT INTO {table_name}
                (detection_id, presence_id, person_id, video_id,
                 frame_index, t_time, x, y, w, h, detection_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, detection_id) DO NOTHING
            """,
            (
                detection_id,
                presence_id,
                person_id,
                video_id,
                getattr(detection, "frameIndex", None),
                getattr(detection, "timeStart", None),
                getattr(detection, "x", None),
                getattr(detection, "y", None),
                getattr(detection, "width", None),
                getattr(detection, "height", None),
                getattr(detection, "detectionScore", None),
            ),
        )


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's face detections and person detections.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")
    _parse_detections(
        cas, cursor, TYPES["face_detection"], "face_detections", video_id, context
    )
    _parse_detections(
        cas, cursor, TYPES["person_detection"], "person_detections", video_id, context
    )
