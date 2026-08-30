"""Shared fixtures for the webapp's tests.

`db_available` reports whether a real Postgres is reachable, using the
same `DUUI_DB_*` settings the webapp itself reads. A test needing a
database skips when none is, rather than failing, so the suite can
still be collected without one.

There is no rollback fixture here, unlike the other two suites. The
tests that do write commit their rows and delete them again, because
the query functions under test open their own connections: work left
uncommitted inside a test's transaction would be invisible to them.

`docker compose run --rm tests` provides the database and applies the
schema.
"""

import pytest

# Imported defensively, so this file can be loaded without the webapp's
# own dependencies installed.
#
# conftest.py is imported for *every* test in this directory, including
# the accessibility tests, which read committed CSS, HTML and
# JavaScript and need neither a database nor the backend package. A
# hard import here made "no driver installed" fail collection outright,
# which contradicts what the rest of this file is for: a database-backed
# test is meant to *skip* when there is nothing to connect to, and a
# missing driver is another way of there being nothing to connect to.
try:
    import psycopg2
except ImportError:  # pragma: no cover - depends on the environment
    psycopg2 = None

DB_CONFIG: dict[str, str | int] | None
try:
    from backend.config import DB_CONFIG
except Exception:  # pragma: no cover - backend needs its own dependencies
    DB_CONFIG = None


def _can_connect() -> bool:
    """Whether a database is reachable with the configured settings."""
    if psycopg2 is None or DB_CONFIG is None:
        return False
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
