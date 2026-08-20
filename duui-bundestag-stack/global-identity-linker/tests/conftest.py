"""
Shared fixtures for the global-identity job's test suite.

`db_conn`/`db_cursor` give tests a real Postgres connection (using the
same DUUI_DB_* env vars/`.env` the job itself reads via
identity.config.DB_CONFIG) and roll back everything at teardown --
tests are free to INSERT/UPDATE against the real schema and never have
to clean up by hand, as long as they never call `conn.commit()`
themselves. Tests that need a live DB are automatically skipped (not
failed) if one isn't reachable, so `pytest` still works for anyone who
just wants to collect the suite without spinning up Postgres.

That rollback matters more here than in the other two suites: this job
deliberately deletes every row in `global_persons`, so a test that
exercises the real wipe would otherwise destroy a populated database.
Nothing here commits, so nothing here escapes the transaction.

Requires the schema already applied (`psql -f pgvector-db/schema.sql`) --
see README "Tests" for how CI does this.
"""

import psycopg2
import pytest

from identity.config import DB_CONFIG


def _can_connect():
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=2)
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


@pytest.fixture(scope="session")
def db_available():
    return _can_connect()


@pytest.fixture
def db_conn(db_available):
    if not db_available:
        pytest.skip(
            "No Postgres reachable via DUUI_DB_* env vars -- set them "
            "(or run against docker-compose's db service) to run DB-backed tests."
        )
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        # Never commit in a test -- this is the entire cleanup
        # mechanism, so every insert/update a test makes disappears
        # regardless of whether the test passed or failed.
        conn.rollback()
        conn.close()


@pytest.fixture
def db_cursor(db_conn):
    cur = db_conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
