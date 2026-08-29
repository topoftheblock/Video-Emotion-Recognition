"""Reads the video row, and establishes what the video is called.

Read from MultimediaElement, falling back to DocumentMetaData when no
MultimediaElement annotation is present.

Sets `global_video_id` and `video_filename` in the context for the
steps that follow. `pipeline.py` uses the latter after the commit, to
place the companion video file where the webapp expects it, so the name
stays in lockstep with whatever ended up in the `videos` row rather
than being derived a second time.

**The video is keyed by filename**, and `video_id` is whatever the
database assigns. It was once the identifying annotation's `xmi:id`,
which is a per-document counter: every CAS exported by one pipeline
numbers its DocumentMetaData the same way, so files declaring
`xmi:id=3` all claimed the same `videos` row and merged into each
other. The filename is the only identifier stable per video, and it is
already the join key to the video store the webapp plays from. See the
identity note in `pgvector-db/schema.sql`.
"""

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

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


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Upsert the video row and record its id and filename.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    global_video_id = None
    # `pipeline.py` reads the filename off the raw XML before the CAS
    # is loaded, since it needs it to decide skip or replace without
    # paying for a cassis parse. When it did, that is the filename this
    # row must use: one identity, established once.
    video_filename = context.get("video_filename")

    # `select_exact_type`, not `select_across_views`: MultimediaElement
    # is the common supertype of most time-bounded annotations here —
    # Shot, Detection, SpeakerSegment, Emotion — so a subtype-inclusive
    # select would match one of those instead of the video record.
    for multimedia in select_exact_type(cas, TYPES["multimedia_element"]):
        # videos.filename is NOT NULL, so fall back to a placeholder
        # rather than letting the insert fail if a MultimediaElement
        # instance ever lacks one.
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


def read_identity(cas: Cas) -> str | None:
    """Return the filename this CAS describes, without a database hit.

    Same precedence as `parse`: MultimediaElement, then
    DocumentMetaData. Used as `pipeline.py`'s fallback when the earlier
    read off the raw XML came up empty, so the two paths cannot
    disagree about what the video is called.

    Args:
        cas: The loaded CAS.

    Returns:
        The filename, or None if no identifying annotation carries one.
    """
    for multimedia in select_exact_type(cas, TYPES["multimedia_element"]):
        return getattr(multimedia, "filename", None) or "unknown"
    for md in select_across_views(cas, TYPES["document_meta_data"]):
        return getattr(md, "documentTitle", None) or "unknown"
    return None
