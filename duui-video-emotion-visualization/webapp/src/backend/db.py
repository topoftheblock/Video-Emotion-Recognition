"""Database connections and one-shot queries for the webapp."""

from typing import Any

import psycopg2
from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor

from .config import DB_CONFIG


def get_db_connection() -> connection:
    """Open a new database connection.

    The caller owns the connection and is responsible for closing it.
    """
    return psycopg2.connect(**DB_CONFIG)


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Run one query and return its rows as plain dicts.

    One connection per call, opened and closed here. That is more
    round-trips than a pool would need, but `query_agent/sql_guard.py`
    puts a connection into a READ ONLY session before running
    LLM-generated SQL on it, and closing that connection is what
    discards the setting. A pool would hand it back still read-only, so
    pooling means resetting session state on release.

    Args:
        sql: The statement to run.
        params: Its parameters, if any.

    Returns:
        One dict per row, in the order the database returned them.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
