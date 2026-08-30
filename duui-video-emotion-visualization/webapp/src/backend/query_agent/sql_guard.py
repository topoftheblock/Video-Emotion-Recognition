"""Guardrails for running model-written SQL against the database.

Two layers, because neither alone is trustworthy against a model that
may emit something unexpected:

1. A textual check that the statement is a single read-only `SELECT`,
   optionally led by `WITH`. It rejects multi-statement input and any
   statement carrying a writing keyword.
2. A read-only Postgres session, which the engine itself enforces
   whatever slipped past the first layer.

On top of those, every query is capped to `QUERY_AGENT_MAX_ROWS` by
wrapping it in an outer `LIMIT`, and a statement timeout bounds how
long a bad query can run — a missing join condition producing a huge
cross product, say.

The first layer is deliberately blunt. It matches keywords anywhere in
the text, so a query mentioning one inside a string literal is refused
even though it would have been harmless. Refusing a valid query is
recoverable, since the model is told why and can try again; the
opposite is not.
"""

import re
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from ..config import QUERY_AGENT_MAX_ROWS, QUERY_AGENT_STATEMENT_TIMEOUT_MS
from ..db import get_db_connection

# Keywords that must never appear in the model's SQL, including inside
# a CTE. Checked as text, before the database is involved at all.
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|"
    r"COPY|CALL|EXECUTE|VACUUM|REINDEX|LISTEN|NOTIFY|SET|RESET|"
    r"LOCK|MERGE|REFRESH)\b",
    re.IGNORECASE,
)

_LEADING_KEYWORD = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE)


class SQLGuardError(ValueError):
    """Raised when a candidate query fails the safety checks."""


def validate_select_only(sql: str) -> str:
    """Check that a statement is a single read-only query.

    Args:
        sql: The candidate statement.

    Returns:
        The statement, trimmed of surrounding space and any trailing
        semicolon.

    Raises:
        SQLGuardError: If it is empty, holds more than one statement,
            does not begin with SELECT or WITH, or carries a forbidden
            keyword.
    """
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise SQLGuardError("Empty query.")
    if ";" in stripped:
        raise SQLGuardError("Multiple statements are not allowed.")
    if not _LEADING_KEYWORD.match(stripped):
        raise SQLGuardError("Query must start with SELECT or WITH.")
    if _FORBIDDEN_KEYWORDS.search(stripped):
        raise SQLGuardError(
            "Query contains a keyword that is not allowed in this "
            "read-only agent (only SELECT/WITH queries are permitted)."
        )
    return stripped


def run_read_only(
    sql: str, row_limit: int | None = None
) -> tuple[list[str], list[dict[str, Any]], bool]:
    """Validate a query, then run it read-only and row-capped.

    Args:
        sql: The statement to run.
        row_limit: The row cap; `QUERY_AGENT_MAX_ROWS` when not given.

    Returns:
        The column names, the rows as plain dicts, and whether the cap
        actually cut anything off.

    Raises:
        SQLGuardError: If validation fails, or the database rejects the
            query.
    """
    validated = validate_select_only(sql)
    limit = row_limit or QUERY_AGENT_MAX_ROWS
    # One extra row, so the cap can be told from a result that simply
    # ended, without a second round-trip to count.
    wrapped = f"SELECT * FROM ({validated}) AS _sub LIMIT %s"

    conn = get_db_connection()
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SET LOCAL statement_timeout = {QUERY_AGENT_STATEMENT_TIMEOUT_MS}"
            )
            cur.execute(wrapped, (limit + 1,))
            rows = [dict(row) for row in cur.fetchall()]
            columns = (
                list(rows[0].keys())
                if rows
                else ([d.name for d in cur.description] if cur.description else [])
            )
        conn.rollback()
    except psycopg2.Error as exc:
        conn.rollback()
        raise SQLGuardError(str(exc).strip()) from exc
    finally:
        conn.close()

    truncated = len(rows) > limit
    return columns, rows[:limit], truncated
