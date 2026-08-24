"""Parses FaceDetection and PersonDetection rows.

Both share the same shape (presence/person/frame/bbox/score), so a
single helper handles both tables.
"""

from ..cas.person_resolution import resolve_person_id_via_face_fs
from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def _resolve_detection_person_id(detection, context):
    track = getattr(detection, "track", None)
    if track and getattr(track, "face", None):
        return resolve_person_id_via_face_fs(track.face, context)
    return None


def _parse_detections(cas, cursor, uima_type, table_name, video_id, context):
    for detection in select_across_views(cas, uima_type):
        detection_id = get_xmi_id(detection)
        presence_id = get_xmi_id(getattr(detection, "track", None))
        person_id = _resolve_detection_person_id(detection, context)

        cursor.execute(
            f"""
            INSERT INTO {table_name} (detection_id, presence_id, person_id, video_id, frame_index, t_time, x, y, w, h, detection_score)
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


def parse(cas, cursor, context):
    video_id = context.get("global_video_id")
    _parse_detections(
        cas, cursor, TYPES["face_detection"], "face_detections", video_id, context
    )
    _parse_detections(
        cas, cursor, TYPES["person_detection"], "person_detections", video_id, context
    )
