"""Database connections for the importer."""

import psycopg2
from psycopg2.extensions import connection

from .config import DB_CONFIG


def get_db_connection() -> connection:
    """Open a new database connection.

    The caller owns the connection and is responsible for closing it.
    """
    return psycopg2.connect(**DB_CONFIG)


def find_video_by_filename(filename: str | None) -> int | None:
    """Return the video_id already imported under `filename`, or None.

    Uses its own short-lived connection on purpose. This runs *before*
    the import's transaction exists, to decide whether opening that
    transaction is worth it at all — see the skip and replace handling
    in `pipeline.run`.
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


def delete_video(video_id: int) -> None:
    """Remove a video and everything hanging off it.

    One statement does it: every table referencing `videos` does so with
    ON DELETE CASCADE, and the per-video composite keys mean that
    subtree is exactly this video's rows and nothing else — see
    `pgvector-db/schema.sql`.

    Committed on its own, because `--on-existing replace` should leave
    the old rows gone even if the re-import that follows then fails on a
    malformed CAS. The state is then "not imported", rather than a
    half-updated mixture of two exports.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE video_id = %s", (video_id,))
        conn.commit()
    finally:
        conn.close()
