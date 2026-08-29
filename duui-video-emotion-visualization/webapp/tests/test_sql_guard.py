"""Tests for the read-only guard the agent's queries run through.

This is a real safety boundary — the model's output is untrusted input
— so it is tested independently of whether a model is configured at all.
"""

import pytest

from backend.query_agent.sql_guard import (
    SQLGuardError,
    run_read_only,
    validate_select_only,
)

# --- Validation ---------------------------------------------------------
# No database needed: this layer is pure text.


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "select * from videos",
        "  SELECT 1  ",
        "SELECT 1;",  # a single trailing semicolon is stripped, not rejected
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "with x as (select 1) select * from x",
    ],
)
def test_validate_select_only_accepts(sql: str) -> None:
    """A single read-only query passes, and comes back trimmed."""
    assert validate_select_only(sql) == sql.strip().rstrip(";").strip()


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "DROP TABLE videos",
        "INSERT INTO videos (filename) VALUES ('x')",
        "UPDATE videos SET filename = 'x'",
        "DELETE FROM videos",
        "CREATE TABLE evil (id int)",
        "GRANT ALL ON videos TO public",
        "SELECT 1; DROP TABLE videos",
        "not sql at all",
    ],
)
def test_validate_select_only_rejects(sql: str) -> None:
    """Anything writing, empty, or multi-statement is refused."""
    with pytest.raises(SQLGuardError):
        validate_select_only(sql)


def test_validate_select_only_rejects_keyword_hidden_in_cte() -> None:
    """A write hidden inside a CTE is still a write."""
    with pytest.raises(SQLGuardError):
        validate_select_only(
            "WITH x AS (DELETE FROM videos RETURNING *) SELECT * FROM x"
        )


# --- Execution ----------------------------------------------------------
# These need a live database, and skip without one.


def test_run_read_only_executes_select(db_available: bool) -> None:
    """A valid query runs, and its columns and rows come back."""
    if not db_available:
        pytest.skip("no DB reachable")
    columns, rows, truncated = run_read_only("SELECT 1 AS one, 'x' AS two")
    assert columns == ["one", "two"]
    assert rows == [{"one": 1, "two": "x"}]
    assert truncated is False


def test_run_read_only_caps_rows_and_reports_truncation(db_available: bool) -> None:
    """The row cap holds, and says when it cut something off."""
    if not db_available:
        pytest.skip("no DB reachable")
    columns, rows, truncated = run_read_only(
        "SELECT generate_series(1, 10) AS n", row_limit=3
    )
    assert len(rows) == 3
    assert truncated is True


def test_run_read_only_blocks_writes_even_past_validation(db_available: bool) -> None:
    """The second layer holds on its own.

    Even were the textual check bypassed, the read-only session must
    still refuse a write.
    """
    if not db_available:
        pytest.skip("no DB reachable")
    with pytest.raises(SQLGuardError):
        run_read_only("DROP TABLE videos")
