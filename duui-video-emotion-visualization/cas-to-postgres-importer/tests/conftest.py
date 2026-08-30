"""Shared fixtures for the importer's tests.

`db_conn` and `db_cursor` hand a test a real Postgres connection, using
the same `DUUI_DB_*` settings the importer itself reads, and roll
everything back at teardown. A test may INSERT and UPDATE against the
real schema and never clean up by hand, **so long as it never commits**.

A test needing a database skips when none is reachable, rather than
failing, so the suite can still be collected without one.

`docker compose run --rm tests` provides the database and applies the
schema.
"""

from collections.abc import Iterator

import psycopg2
import pytest
from psycopg2.extensions import connection, cursor

from importer.config import DB_CONFIG


def _can_connect() -> bool:
    """Whether a database is reachable with the configured settings."""
    try:
        # Overriding the key rather than passing it a second time:
        # DB_CONFIG carries a connect_timeout of its own, and a second
        # keyword would be a TypeError. Two seconds because this only
        # decides whether to skip the suite, and waiting the full
        # connect timeout to answer that would slow every run on a
        # machine with no database.
        conn = psycopg2.connect(**{**DB_CONFIG, "connect_timeout": 2})
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


@pytest.fixture(scope="session")
def db_available() -> bool:
    """Checked once a session: an unreachable database waits once."""
    return _can_connect()


@pytest.fixture
def db_conn(db_available: bool) -> Iterator[connection]:
    """A connection whose work is rolled back when the test ends."""
    if not db_available:
        pytest.skip(
            "No Postgres reachable via DUUI_DB_* env vars — set them "
            "(or run against docker-compose's db service) to run DB-backed tests."
        )
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        # Never commit in a test — this is the entire cleanup mechanism,
        # so every insert/update a test makes disappears regardless of
        # whether the test passed or failed.
        conn.rollback()
        conn.close()


@pytest.fixture
def db_cursor(db_conn: connection) -> Iterator[cursor]:
    """A cursor on `db_conn`, closed when the test ends."""
    cur = db_conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
