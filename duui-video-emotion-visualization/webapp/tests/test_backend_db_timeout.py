"""Tests that every database connection is bounded by a timeout.

Without one, `psycopg2.connect` waits on the operating system's TCP
timeout: against a host that accepts the route but never answers, that
is minutes with nothing printed. The setting lives in `DB_CONFIG` rather
than at each call site, so every connection in this sub-project inherits
it.

The file is named for the package it covers because the three suites are
collected together, and pytest identifies a test module by its basename
alone — three files called `test_db_timeout` would collide.

No database is needed: these read the configuration, not a connection.
"""

import importlib
from collections.abc import Iterator

import pytest

from backend import config


@pytest.fixture(autouse=True)
def _restore_config() -> Iterator[None]:
    """Re-read the module after, so other tests see the defaults."""
    yield
    importlib.reload(config)


def test_db_config_carries_a_connect_timeout() -> None:
    """Every connection built from DB_CONFIG is bounded."""
    assert "connect_timeout" in config.DB_CONFIG


def test_the_timeout_is_a_whole_number_of_seconds() -> None:
    """psycopg2 wants a number, not the string from the environment."""
    assert isinstance(config.DB_CONFIG["connect_timeout"], int)


def test_the_default_is_ten_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset, the timeout is the project-wide default."""
    monkeypatch.delenv("DUUI_DB_CONNECT_TIMEOUT", raising=False)
    reloaded = importlib.reload(config)

    assert reloaded.DB_CONFIG["connect_timeout"] == 10


def test_the_timeout_is_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployment on a slow network can raise it."""
    monkeypatch.setenv("DUUI_DB_CONNECT_TIMEOUT", "42")
    reloaded = importlib.reload(config)

    assert reloaded.DB_CONFIG["connect_timeout"] == 42
