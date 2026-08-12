"""High-level orchestration: load a CAS, run every parser step against
it inside one DB transaction, commit, then place the companion video
file where the webapp expects it.
"""

from pathlib import Path

from cassis import load_cas_from_xmi

from .config import XMI_FILE
from .db import get_db_connection
from .media import place_video_file
from .parsers import PARSE_STEPS
from .typesystem import load_merged_typesystem


def parse_and_insert(cas, cursor, conn):
    """
    Run all registered parser steps against a single loaded CAS.

    `context` is threaded through every step so later steps (Segment,
    Person, Presence, Detection, Emotion, ...) can read
    context["global_video_id"], which the video step resolves first.
    Returned so `run()` can use context["video_filename"] afterwards.
    """
    context = {}
    for step in PARSE_STEPS:
        step.parse(cas, cursor, conn, context)
    return context


def run(xmi_file=None):
    """Load typesystem + CAS, parse, commit to the database, and place
    the video file that came alongside the CAS (same directory, same
    filename as the `videos` row) into VIDEO_MEDIA_DIR."""
    xmi_file = xmi_file or XMI_FILE

    print("Loading and patching TypeSystems...")
    merged_typesystem = load_merged_typesystem()

    print("Loading CAS data from XMI...")
    with open(xmi_file, "rb") as f:
        # trusted=True enables lxml's huge_tree parsing, needed for large
        # multi-hour-session XMI exports that exceed lxml's default buffer.
        cas = load_cas_from_xmi(f, typesystem=merged_typesystem, lenient=True, trusted=True)

    print("Connecting to database and inserting data...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        context = parse_and_insert(cas, cursor, conn)
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # A CAS always arrives paired with its source video in the same
    # input directory (see README "Docker architecture") -- look for
    # it right next to the .xmi file just parsed.
    place_video_file(context.get("video_filename"), Path(xmi_file).parent)

    print("Parser completed successfully!")
