"""Parses the Video row from MultimediaElement, falling back to
DocumentMetaData if no MultimediaElement annotation is present.

Sets context["global_video_id"] for downstream parsers.
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..db import get_or_insert_id
from ..typesystem import get_xmi_id


def parse(cas, cursor, conn, context):
    global_video_id = None

    for multimedia in select_across_views(cas, TYPES["multimedia_element"]):
        global_video_id = get_xmi_id(multimedia)
        get_or_insert_id(cursor, conn, "Video", "video_id", global_video_id)
        cursor.execute(
            """
            INSERT INTO Video (video_id, filename, duration, processed_at, fps, width, height)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
                filename = EXCLUDED.filename, duration = EXCLUDED.duration,
                processed_at = EXCLUDED.processed_at, fps = EXCLUDED.fps,
                width = EXCLUDED.width, height = EXCLUDED.height
            """,
            (
                global_video_id,
                getattr(multimedia, "filename", None),
                getattr(multimedia, "duration", None),
                getattr(multimedia, "processed_at", None),
                getattr(multimedia, "fps", None),
                getattr(multimedia, "width", None),
                getattr(multimedia, "height", None),
            ),
        )
        break

    if not global_video_id:
        for md in select_across_views(cas, TYPES["document_meta_data"]):
            global_video_id = get_xmi_id(md)
            get_or_insert_id(cursor, conn, "Video", "video_id", global_video_id)
            cursor.execute(
                "INSERT INTO Video (video_id, filename) VALUES (%s, %s) "
                "ON CONFLICT (video_id) DO NOTHING",
                (global_video_id, getattr(md, "documentTitle", None)),
            )
            break

    context["global_video_id"] = global_video_id
