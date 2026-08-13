"""Parses the Video row from MultimediaElement, falling back to
DocumentMetaData if no MultimediaElement annotation is present.

Sets context["global_video_id"] and context["video_filename"] for
downstream steps -- the latter is what pipeline.py uses after commit
to place the companion video file where the webapp expects it (see
duui_parser/media.py), so it stays in lockstep with whatever filename
actually ended up in the `videos` row, rather than being re-derived.
"""

from ..cas_views import select_across_views, select_exact_type
from ..config import TYPES
from ..typesystem import get_xmi_id


def parse(cas, cursor, conn, context):
    global_video_id = None
    video_filename = None

    # `select_exact_type`, not `select_across_views`: MultimediaElement
    # is the common supertype of most time-bounded annotations in this
    # pipeline (Shot, Detection, SpeakerSegment, Emotion, ...), so a
    # plain subtype-inclusive select would match one of those instead
    # of an actual top-level video record.
    for multimedia in select_exact_type(cas, TYPES["multimedia_element"]):
        global_video_id = get_xmi_id(multimedia)
        # videos.filename is NOT NULL -- fall back to a placeholder
        # rather than letting the insert fail if a real
        # MultimediaElement instance ever lacks one.
        video_filename = getattr(multimedia, "filename", None) or "unknown"
        cursor.execute(
            """
            INSERT INTO videos (video_id, filename, duration, processed_at, fps, width, height)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id) DO UPDATE SET
                filename = EXCLUDED.filename, duration = EXCLUDED.duration,
                processed_at = EXCLUDED.processed_at, fps = EXCLUDED.fps,
                width = EXCLUDED.width, height = EXCLUDED.height
            """,
            (
                global_video_id,
                video_filename,
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
            video_filename = getattr(md, "documentTitle", None) or "unknown"
            cursor.execute(
                "INSERT INTO videos (video_id, filename) VALUES (%s, %s) "
                "ON CONFLICT (video_id) DO NOTHING",
                (global_video_id, video_filename),
            )
            break

    context["global_video_id"] = global_video_id
    context["video_filename"] = video_filename
