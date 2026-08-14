"""Database connection handling."""

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import DB_CONFIG


def get_db_connection():
    """Open a new psycopg2 connection using DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)


def query(sql, params=None):
    """
    Run one query and return a list of plain dict rows.

    One connection per call, opened and closed here. That is more
    round-trips than a pooled connection would need, but the read-only
    agent's guard (query_agent/sql_guard.py) flips a connection into a
    READ ONLY session before handing it back, so a pool would need to
    reset that state before reuse -- see README before changing this.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
