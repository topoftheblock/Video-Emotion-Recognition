"""
Guardrails for running LLM-generated SQL against the real database.

Two layers, because neither alone is trustworthy against an LLM that
might emit something unexpected:
  1. A syntactic check that the statement is a single read-only
     `SELECT`/`WITH ... SELECT` -- rejects multi-statement input and
     any DML/DDL keyword.
  2. A `SET TRANSACTION READ ONLY` Postgres transaction, which the
     engine itself enforces regardless of what slipped past (1).

On top of that: every query is capped to `QUERY_AGENT_MAX_ROWS` rows
by wrapping it in an outer `SELECT * FROM (<query>) AS _sub LIMIT n`,
and a statement timeout bounds how long a bad query (e.g. a missing
join condition producing a huge cross product) can run.
"""

import re

import psycopg2
from psycopg2.extras import RealDictCursor

from ..config import QUERY_AGENT_MAX_ROWS, QUERY_AGENT_STATEMENT_TIMEOUT_MS
from ..db import get_db_connection

# Keywords that must never appear in agent-generated SQL, even inside
# a CTE -- this is a blunt but effective belt-and-suspenders check
# alongside the READ ONLY transaction.
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
    """
    Raise SQLGuardError unless `sql` is a single SELECT (optionally
    preceded by WITH ... ) statement. Returns the trimmed statement.
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


def run_read_only(sql: str, row_limit: int = None):
    """
    Validate and execute `sql` as a read-only, row-capped query.

    Returns (columns, rows, truncated) where `rows` is a list of plain
    dicts and `truncated` is True if the result was cut off by the row
    cap (i.e. more rows existed than we returned).
    """
    validated = validate_select_only(sql)
    limit = row_limit or QUERY_AGENT_MAX_ROWS
    # Fetch one extra row so we can tell whether the cap actually
    # truncated anything, without a separate COUNT(*) round-trip.
    wrapped = f"SELECT * FROM ({validated}) AS _sub LIMIT %s"

    conn = get_db_connection()
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET LOCAL statement_timeout = {QUERY_AGENT_STATEMENT_TIMEOUT_MS}")
            cur.execute(wrapped, (limit + 1,))
            rows = [dict(row) for row in cur.fetchall()]
            columns = list(rows[0].keys()) if rows else (
                [d.name for d in cur.description] if cur.description else []
            )
        conn.rollback()
    except psycopg2.Error as exc:
        conn.rollback()
        raise SQLGuardError(str(exc).strip()) from exc
    finally:
        conn.close()

    truncated = len(rows) > limit
    return columns, rows[:limit], truncated
