"""
Shared fixtures for the webapp's test suite.

`db_available` reports whether a real Postgres is reachable using the
same DUUI_DB_* env vars/`.env` the viewer itself reads via
backend.config.DB_CONFIG. Tests that need a live DB skip (not
fail) when there isn't one, so `pytest` still works for anyone who
just wants the pure-function tests without spinning up Postgres.

The viewer only ever reads, so unlike the importer's suite (see
cas-to-postgres-importer/tests/conftest.py) nothing here
needs a rollback fixture.

Requires the schema already applied (`psql -f pgvector-db/schema.sql`) --
see README "Tests" for how to run against the compose db service.
"""

import pytest

# Imported defensively so this file can be loaded without the viewer's
# own dependencies installed.
#
# conftest.py is imported for *every* test in this directory, including
# the accessibility suite (test_contrast, test_palette, test_markup,
# test_stylesheets, test_scripts), which reads committed CSS, HTML and
# JavaScript and needs neither a database nor the backend package. A
# hard import here made "no driver installed" fail collection outright,
# which contradicts what the rest of this file is for: the DB-backed
# tests are meant to *skip* when there is nothing to connect to, and a
# missing driver is just another way of there being nothing to connect
# to.
try:
    import psycopg2
except ImportError:  # pragma: no cover - depends on the environment
    psycopg2 = None

try:
    from backend.config import DB_CONFIG
except Exception:  # pragma: no cover - backend needs its own dependencies
    DB_CONFIG = None


def _can_connect():
    if psycopg2 is None or DB_CONFIG is None:
        return False
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=2)
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


@pytest.fixture(scope="session")
def db_available():
    return _can_connect()
