"""Tests for the style checker itself.

`stylecheck.py` is the only enforcement several style-guide rules have,
so a bug in it is silent: the check passes and the rule stops existing.
Phase 8 extended it to file types it could not read before, and SQL is
the delicate one — `--` is both the comment marker and the legacy em
dash the checker looks for, so a naive rule reports every comment line
in `schema.sql` as a finding.

These tests write a file, run one check over it, and assert on the
findings. They never touch the repository's own files, so a real
violation somewhere else cannot make one pass or fail.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import stylecheck  # noqa: E402


def kinds(path: pathlib.Path) -> list[str]:
    """Return the finding kinds `check_file` reports for one file."""
    return [kind for _, kind, _ in stylecheck.check_file(path, exempt=False)]


def messages(path: pathlib.Path) -> list[str]:
    """Return the finding messages `check_file` reports for one file."""
    return [message for _, _, message in stylecheck.check_file(path, exempt=False)]


def write(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    """Write `body` to `name` under `tmp_path` and return the path."""
    path = tmp_path / name
    path.write_text(body)
    return path


# --- SQL ----------------------------------------------------------------


def test_a_plain_sql_comment_is_not_an_em_dash(tmp_path: pathlib.Path) -> None:
    """The `--` that opens a SQL comment is a marker, not a dash.

    The rule this guards is the whole reason `.sql` support needed a
    test: every comment line in the schema starts with the sequence the
    em-dash rule looks for.
    """
    path = write(tmp_path, "a.sql", "-- One row per job run.\nSELECT 1;\n")
    assert kinds(path) == []


def test_a_real_em_dash_inside_a_sql_comment_is_found(tmp_path: pathlib.Path) -> None:
    """A legacy `--` between words is still a finding in SQL."""
    path = write(
        tmp_path, "a.sql", "-- A shot has no speaker -- so the column is null.\n"
    )
    assert kinds(path) == ["emdash"]


def test_an_over_wide_sql_comment_is_found(tmp_path: pathlib.Path) -> None:
    """Prose in a SQL comment wraps at 72 like prose anywhere else.

    Asserting the message, not just the kind: without a `.sql` branch
    the same line trips the 88-column *code* rule instead, which is a
    different rule reporting a different number and would let this pass
    while the prose limit went unenforced.
    """
    path = write(tmp_path, "a.sql", "-- " + "word " * 20 + "\n")
    assert messages(path) == ["prose 103 > 72"]


def test_sql_code_is_not_measured_as_prose(tmp_path: pathlib.Path) -> None:
    """A statement is code, and code is allowed 88 columns."""
    statement = "SELECT " + "a, " * 22 + "b FROM t;"
    assert stylecheck.PROSE_WIDTH < len(statement) < stylecheck.CODE_WIDTH
    path = write(tmp_path, "a.sql", statement + "\n")
    assert kinds(path) == []


def test_a_retired_term_in_a_sql_comment_is_found(tmp_path: pathlib.Path) -> None:
    """The glossary binds SQL comments too."""
    path = write(tmp_path, "a.sql", "-- What the viewer reads.\n")
    assert "term" in kinds(path)


# --- The other newly covered kinds --------------------------------------


@pytest.mark.parametrize("name", [".env.example", ".yamllint", "pre-commit"])
def test_hash_comment_files_are_checked(name: str, tmp_path: pathlib.Path) -> None:
    """Files named rather than suffixed still get read."""
    path = write(tmp_path, name, "# " + "word " * 20 + "\n")
    assert kinds(path) == ["width"]


def test_a_c_comment_config_is_checked(tmp_path: pathlib.Path) -> None:
    """`.cjs` and `.jsonc` carry prose in `//` comments."""
    path = write(tmp_path, "a.cjs", "// " + "word " * 20 + "\n")
    assert kinds(path) == ["width"]


def test_a_quoted_command_is_exempt_from_the_width_rule(
    tmp_path: pathlib.Path,
) -> None:
    """An indented command in a comment is quoted, not wrapped."""
    path = write(tmp_path, "a.sh", "#     " + "docker-compose-" * 6 + "\n")
    assert kinds(path) == []


def test_ordinary_prose_is_still_measured(tmp_path: pathlib.Path) -> None:
    """The exemption needs the indent; one space is not quoting."""
    path = write(tmp_path, "a.sh", "# " + "word " * 20 + "\n")
    assert kinds(path) == ["width"]


def test_a_file_no_rule_matches_is_skipped(tmp_path: pathlib.Path) -> None:
    """`collect` decides what is read; nothing else should be."""
    write(tmp_path, "notes.rst", "# " + "word " * 20 + "\n")
    assert stylecheck.collect(tmp_path) == []


# --- US English ---------------------------------------------------------


@pytest.mark.parametrize(
    ("british", "american"),
    [
        ("colour", "color"),
        ("behaviour", "behavior"),
        ("judgement", "judgment"),
        ("artefact", "artifact"),
        ("grey", "gray"),
        # A stem, because -ise/-ize covers a family of endings and the
        # suggestion is the part that changes.
        ("recognise", "recogniz"),
    ],
)
def test_a_british_spelling_is_found(
    british: str, american: str, tmp_path: pathlib.Path
) -> None:
    """§8 of the guide says US English, in prose and in identifiers."""
    path = write(tmp_path, "a.sh", f"# The {british} of it.\n")
    assert kinds(path) == ["spelling"]
    assert american in messages(path)[0]


def test_the_american_spelling_is_not_found(tmp_path: pathlib.Path) -> None:
    """The rule fires on the British form only."""
    path = write(tmp_path, "a.sh", "# The color of it.\n")
    assert kinds(path) == []


def test_a_british_spelling_inside_an_identifier_is_found(
    tmp_path: pathlib.Path,
) -> None:
    """The guide binds identifiers, so a word boundary is not enough."""
    body = '"""Doc."""\n\n\ndef load_colours() -> None:\n    """Doc."""\n'
    assert "spelling" in kinds(write(tmp_path, "a.py", body))


def test_aria_labelledby_is_not_a_spelling_error(tmp_path: pathlib.Path) -> None:
    """An ARIA attribute contains `labelled` and is spelled correctly.

    The rename this rule guards would have corrupted twelve of these if
    it had matched on the substring alone.
    """
    path = write(tmp_path, "a.html", "<!-- aria-labelledby resolves -->\n")
    assert kinds(path) == []


def test_the_ubuntu_font_licence_keeps_its_name(tmp_path: pathlib.Path) -> None:
    """A license's actual name is not a spelling to correct."""
    path = write(tmp_path, "a.sh", "# Under the Ubuntu Font Licence 1.0.\n")
    assert kinds(path) == []


# --- Markdown, which gets the spelling rule and nothing else ------------


def test_the_glossary_may_name_the_terms_it_retires(tmp_path: pathlib.Path) -> None:
    """Markdown gets the spelling rule and not the glossary rule.

    The document that lists every retired term is the glossary, and it
    has to write them down in order to retire them.
    """
    path = write(tmp_path, "a.md", 'Use "the webapp", never "viewer".\n')
    assert kinds(path) == []


def test_a_british_spelling_in_markdown_is_found(tmp_path: pathlib.Path) -> None:
    """The documents held most of Phase 8's 185 occurrences."""
    path = write(tmp_path, "a.md", "The colour of it.\n")
    assert kinds(path) == ["spelling"]


def test_markdown_prose_is_not_measured_at_72(tmp_path: pathlib.Path) -> None:
    """Markdown wraps at 80, which markdownlint already enforces.

    Applying this checker's 72-column rule to Markdown would
    contradict the guide and duplicate a tool that owns it.
    """
    path = write(tmp_path, "a.md", "word " * 16 + "\n")
    assert kinds(path) == []


def test_a_markdown_table_is_not_measured_at_88(tmp_path: pathlib.Path) -> None:
    """Markdown width belongs to markdownlint, at 80 and with exempts.

    A table row cannot be wrapped, and markdownlint exempts tables for
    exactly that reason. Measuring them here as code would report every
    document in the project.
    """
    path = write(tmp_path, "a.md", "| " + "cell | " * 20 + "\n")
    assert kinds(path) == []


def test_a_markdown_code_fence_is_not_read_as_prose(tmp_path: pathlib.Path) -> None:
    """A documented flag is not a legacy em dash."""
    path = write(tmp_path, "a.md", "```bash\ngit diff --cached -- src/\n```\n")
    assert kinds(path) == []


def test_the_plan_is_exempt_from_the_spelling_rule(tmp_path: pathlib.Path) -> None:
    """`docs/plan/` records what was found on a date; it is evidence.

    Rewriting it to fix a spelling edits the record rather than
    the software, which is why the owner excluded it.
    """
    plan = tmp_path / "docs" / "plan"
    plan.mkdir(parents=True)
    path = plan / "phase-1.md"
    path.write_text("The colour it was then.\n")
    assert kinds(path) == []


# --- Rules that already existed, so the extension cannot break them -----


def test_a_legacy_em_dash_in_python_prose_is_found(tmp_path: pathlib.Path) -> None:
    """The original em-dash rule still fires where it always did."""
    path = write(tmp_path, "a.py", '"""Do a thing -- and another."""\n')
    assert "emdash" in kinds(path)


def test_a_malformed_banner_is_found(tmp_path: pathlib.Path) -> None:
    """A banner that is not the one permitted form is a finding."""
    path = write(tmp_path, "a.py", '"""Doc."""\n# ---- Wrong ----\n')
    assert "banner" in kinds(path)


def test_a_module_without_a_docstring_is_found(tmp_path: pathlib.Path) -> None:
    """Every module gets a docstring."""
    path = write(tmp_path, "a.py", "x = 1\n")
    assert "docstring" in kinds(path)


def test_a_correct_file_reports_nothing(tmp_path: pathlib.Path) -> None:
    """The checker does not fire on prose that follows the guide."""
    path = write(tmp_path, "a.py", '"""Do a thing — and another."""\n\nx = 1\n')
    assert kinds(path) == []


def test_the_message_names_the_rule(tmp_path: pathlib.Path) -> None:
    """A finding says what to do, not only that something is wrong."""
    body = "-- A shot has no speaker -- so it is null.\n"
    assert "write '—'" in messages(write(tmp_path, "a.sql", body))[0]
