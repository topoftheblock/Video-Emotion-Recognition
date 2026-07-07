"""High-level orchestration: load a CAS, run every parser step against
it inside one DB transaction, and commit.
"""

from cassis import load_cas_from_xmi

from .config import XMI_FILE
from .db import get_db_connection
from .parsers import PARSE_STEPS
from .typesystem import load_merged_typesystem


def parse_and_insert(cas, cursor, conn):
    """
    Run all registered parser steps against a single loaded CAS.

    `context` is threaded through every step so later steps (Segment,
    Person, Presence, Detection, Emotion, ...) can read
    context["global_video_id"], which the video step resolves first.
    """
    context = {}
    for step in PARSE_STEPS:
        step.parse(cas, cursor, conn, context)


def run(xmi_file=None):
    """Load typesystem + CAS, parse, and commit to the database."""
    xmi_file = xmi_file or XMI_FILE

    print("Loading and patching TypeSystems...")
    merged_typesystem = load_merged_typesystem()

    print("Loading CAS data from XMI...")
    with open(xmi_file, "rb") as f:
        cas = load_cas_from_xmi(f, typesystem=merged_typesystem, lenient=True)

    print("Connecting to database and inserting data...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        parse_and_insert(cas, cursor, conn)
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Parser completed successfully!")
