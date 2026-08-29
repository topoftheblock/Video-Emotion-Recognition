"""Session-level reporting for a run that spans all three suites.

Deliberately not a shared fixture. Sub-projects share no files, and each
keeps its own `tests/conftest.py` with its own copy of anything it needs
— see docs/plan/README.md §1. What lives here is the one thing that
cannot live there: a summary of the whole session, which would print
three times if each suite defined it.

Its only job is to make an incomplete run say so. `docker compose run
--rm tests`, the supported way to run the suite, provisions a database
and fails outright if it cannot, so nothing skips on that path. Running
`pytest` directly does not, and the database-backed tests then skip
quietly — 29 of them, in a run that still reports success. That is a
weaker signal than it looks, and this makes it visible.
"""

import pytest

#: A skip reason mentioning any of these is a skip for want of a
#: database, rather than a deliberate exclusion such as a check that
#: cannot run as root.
_DATABASE_WORDS = ("database", "postgres", "db reachable")


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Say plainly when the run skipped tests for want of a database."""
    skipped = terminalreporter.stats.get("skipped", [])
    for_database = [
        report
        for report in skipped
        if any(word in str(report.longrepr).lower() for word in _DATABASE_WORDS)
    ]
    if not for_database:
        return

    total = terminalreporter._numcollected
    terminalreporter.write_sep("=", "incomplete run", red=True)
    terminalreporter.write_line(
        f"{len(for_database)} of {total} tests were skipped because no database "
        "was reachable."
    )
    terminalreporter.write_line(
        "This run did not exercise the database-backed tests. It is not a "
        "full run, whatever the summary line says."
    )
    terminalreporter.write_line("")
    terminalreporter.write_line(
        "    docker compose run --rm tests      # provisions its own database"
    )
