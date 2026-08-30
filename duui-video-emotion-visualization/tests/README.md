# tests

**This directory holds no tests.** The four sub-projects hold those, each in
its own `tests/`. What lives here is the machinery that runs them, plus the
checkers that have nowhere else to live because they cover the whole project at
once.

A directory called `tests` sitting beside four directories that actually
contain tests needs saying out loud, which is what this file is for.

## What is in it

| File | What it is |
| --- | --- |
| `Dockerfile.tests` | The image the `tests` service runs: every sub-project's dependencies at once, on the interpreter the application images use |
| `Dockerfile.lint` | The image the `lint` service runs: every checker in the roster, Python and Node alike |
| `run-tests.sh` | The `tests` entry point — provision the database, then hand everything through to pytest |
| `run-lint.sh` | The `lint` entry point — every checker in one pass, reporting all failures rather than stopping at the first |
| `ensure_test_db.py` | Creates the test database if it is missing and applies the schema |
| `check_links.py` | Checks that every relative Markdown link in the project points at something real |
| `stylecheck.py` | Checks a sub-project against the style guide and the glossary |
| `hooks/pre-commit` | An optional git hook running the fast half of the lint pass before a commit |

## Running them

Both from the stack root:

```bash
docker compose run --rm tests
docker compose run --rm lint
```

Anything after `tests` is passed straight to pytest, so a path narrows the run
and pytest's own flags all work:

```bash
docker compose run --rm tests webapp/tests -k contrast
```

**This is the supported way to run the suite.** The project targets a Python
version that is not installable everywhere, and a checker that cannot parse a
file silently checks nothing — so both run in a container or not at all.

The test runner creates its own empty database and applies the schema to it,
separate from the real one, because the database-backed tests assume they are
the only writer. If pytest is run some other way, those tests skip, and the
summary says so in as many words rather than reporting a clean run.

The lint image is read-only over the source: nothing here rewrites a file, so
it is safe in CI and safe to run mid-edit. `ruff format` and `ruff check --fix`
are deliberately not part of it.

## The pre-commit hook

Optional, and not installed by default. From anywhere in the repository:

```bash
git config core.hooksPath duui-video-emotion-visualization/tests/hooks
```

It runs formatting and lint over staged Python only. The type checker, the link
check and the Node tools stay in CI, where a few seconds cost nothing — a hook
that makes committing slow is a hook people bypass. `git commit --no-verify`
steps over it, deliberately.

Because `core.hooksPath` is repository-wide and this repository holds a dozen
unrelated projects, the hook scopes itself to this directory, the same way the
CI workflow does with its `paths:` filter.

## Where the detail is

- **What each checker covers, and why each one is in the roster** —
  [`docs/plan/README.md`](../docs/plan/README.md) §6.
- **The rules `stylecheck.py` enforces** —
  [`docs/documentation-style.md`](../docs/documentation-style.md) and
  [`docs/glossary.md`](../docs/glossary.md).
- **Where the CI workflow lives, and why it is outside this project** —
  [`docs/operations.md`](../docs/operations.md).
