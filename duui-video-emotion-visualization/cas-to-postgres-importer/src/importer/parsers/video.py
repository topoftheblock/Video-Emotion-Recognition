"""Parses the Video row from MultimediaElement, falling back to
DocumentMetaData if no MultimediaElement annotation is present.

Sets context["global_video_id"] and context["video_filename"] for
downstream steps -- the latter is what pipeline.py uses after commit
to place the companion video file where the webapp expects it (see
src/importer/cas/sofas.py), so it stays in lockstep with whatever filename
actually ended up in the `videos` row, rather than being re-derived.

**The video is keyed by filename**, and `video_id` is whatever the
database assigns. It used to be the identifying annotation's xmi:id,
which is a per-document counter: every CAS in a corpus exported by one
pipeline numbers its DocumentMetaData the same way, so nine files
declaring `xmi:id=3` all claimed the same `videos` row and merged into
one another. The filename is the only identifier that is stable per
video, and it is already the join key to the video store the webapp
plays from. See pgvector-db/schema.sql's identity note.
"""

from ..cas.types import TYPES
from ..cas.views import select_across_views, select_exact_type

_VIDEO_UPSERT = """
    INSERT INTO videos (filename, duration, processed_at, fps, width, height)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (filename) DO UPDATE SET
        duration = EXCLUDED.duration, processed_at = EXCLUDED.processed_at,
        fps = EXCLUDED.fps, width = EXCLUDED.width, height = EXCLUDED.height
    RETURNING video_id
"""

# Same statement for the metadata-only fallback, which has nothing but
# a title: DO UPDATE (not DO NOTHING) so RETURNING still yields the
# existing row's id on a re-import.
_VIDEO_UPSERT_MINIMAL = """
    INSERT INTO videos (filename) VALUES (%s)
    ON CONFLICT (filename) DO UPDATE SET filename = EXCLUDED.filename
    RETURNING video_id
"""


def parse(cas, cursor, context):
    global_video_id = None
    # pipeline.py reads the filename off the raw XML before the CAS is
    # loaded (it needs it to decide skip/replace without paying for a
    # cassis parse). When it did, that is the filename this row must
    # use -- one identity, established once.
    video_filename = context.get("video_filename")

    # `select_exact_type`, not `select_across_views`: MultimediaElement
    # is the common supertype of most time-bounded annotations in this
    # pipeline (Shot, Detection, SpeakerSegment, Emotion, ...), so a
    # plain subtype-inclusive select would match one of those instead
    # of an actual top-level video record.
    for multimedia in select_exact_type(cas, TYPES["multimedia_element"]):
        # videos.filename is NOT NULL -- fall back to a placeholder
        # rather than letting the insert fail if a real
        # MultimediaElement instance ever lacks one.
        video_filename = (
            video_filename or getattr(multimedia, "filename", None) or "unknown"
        )
        cursor.execute(
            _VIDEO_UPSERT,
            (
                video_filename,
                getattr(multimedia, "duration", None),
                getattr(multimedia, "processed_at", None),
                getattr(multimedia, "fps", None),
                getattr(multimedia, "width", None),
                getattr(multimedia, "height", None),
            ),
        )
        global_video_id = cursor.fetchone()[0]
        break

    if not global_video_id:
        for md in select_across_views(cas, TYPES["document_meta_data"]):
            video_filename = (
                video_filename or getattr(md, "documentTitle", None) or "unknown"
            )
            cursor.execute(_VIDEO_UPSERT_MINIMAL, (video_filename,))
            global_video_id = cursor.fetchone()[0]
            break

    # No identifying annotation at all, but the pre-pass found a name:
    # still worth a row, or every annotation below it has nothing to
    # hang off.
    if not global_video_id and video_filename:
        cursor.execute(_VIDEO_UPSERT_MINIMAL, (video_filename,))
        global_video_id = cursor.fetchone()[0]

    context["global_video_id"] = global_video_id
    context["video_filename"] = video_filename


def read_identity(cas):
    """
    The filename this CAS describes, without touching the database.

    Same precedence as parse() -- MultimediaElement, then
    DocumentMetaData -- and used as pipeline.py's fallback when the
    pre-parse read off the raw XML came up empty, so the two paths
    cannot disagree about what the video is called.
    """
    for multimedia in select_exact_type(cas, TYPES["multimedia_element"]):
        return getattr(multimedia, "filename", None) or "unknown"
    for md in select_across_views(cas, TYPES["document_meta_data"]):
        return getattr(md, "documentTitle", None) or "unknown"
    return None
