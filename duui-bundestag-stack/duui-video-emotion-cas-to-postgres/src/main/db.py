"""Database connection handling."""

import psycopg2

from .config import DB_CONFIG


def get_db_connection():
    """Open a new psycopg2 connection using DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)


def find_video_by_filename(filename):
    """
    The video_id already imported under `filename`, or None.

    Its own short-lived connection on purpose: this runs *before* the
    import's transaction exists, to decide whether that transaction is
    worth opening at all (see pipeline.run's skip/replace handling).
    """
    if not filename:
        return None
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT video_id FROM videos WHERE filename = %s", (filename,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def delete_video(video_id):
    """
    Remove a video and everything hanging off it.

    One statement: every table that references `videos` does so with
    ON DELETE CASCADE, and the per-video composite keys mean that
    subtree is exactly this video's rows and nothing else (see
    db/schema.sql). Committed on its own -- `--on-existing replace`
    should leave the old rows gone even if the re-import that follows
    then fails on a malformed CAS, so the state is "not imported"
    rather than a half-updated mixture of two exports.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE video_id = %s", (video_id,))
        conn.commit()
    finally:
        conn.close()
