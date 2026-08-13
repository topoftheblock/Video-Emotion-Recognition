"""
Shared fixtures for the webapp's test suite.

`db_available` reports whether a real Postgres is reachable using the
same DUUI_DB_* env vars/`.env` the viewer itself reads via
duui_webapp.config.DB_CONFIG. Tests that need a live DB skip (not
fail) when there isn't one, so `pytest` still works for anyone who
just wants the pure-function tests without spinning up Postgres.

The viewer only ever reads, so unlike the importer's suite (see
duui-video-emotion-cas-to-postgres/tests/conftest.py) nothing here
needs a rollback fixture.

Requires the schema already applied (`psql -f db/schema.sql`) --
see README "Tests" for how to run against the compose db service.
"""

import psycopg2
import pytest

from duui_webapp.config import DB_CONFIG


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
