#!/bin/sh
# Every checker, in one pass. Reports all failures rather than stopping
# at the first, so one run tells you everything that is wrong.
#
#     docker compose run --rm lint
#
# Read-only: nothing here rewrites a file. `ruff format` and `ruff check
# --fix` are deliberately not run, so this is safe in CI and safe to run
# while editing. Every tool that caches needs somewhere writable: the
# source is mounted read-only on purpose, so that a checker can never
# rewrite what it is checking.
export RUFF_CACHE_DIR=/tmp/ruff-cache
export SQLFLUFF_CACHE_DIR=/tmp/sqlfluff-cache

status=0

# run: a gate. Failing here fails the whole check.
run() {
  name=$1; shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then :; else status=1; printf '!! %s failed\n' "$name"; fi
}

# report: informational. Printed, never fatal.
report() {
  name=$1; shift
  printf '\n--- %s (reported, not gated) ---\n' "$name"
  "$@" || true
}

run "ruff format"  ruff format --check .
run "ruff lint"    ruff check .
# One mypy invocation per sub-project, because each owns a
# `tests/conftest.py` and mypy identifies a module by its name: pass all
# three paths at once and it sees three different files claiming to be
# `conftest`, then stops on the duplicate rather than checking anything.
# The sub-projects do not share files by design, so they are checked the
# way they are built — separately.

# Every sub-project is now held to the full standard: `tests` is checked
# alongside `src`, and every function carries annotations. The list
# stays a list rather than collapsing into one invocation because the
# three `tests/conftest.py` files still collide as duplicate modules if
# passed together.
for project in global-identity-linker cas-to-postgres-importer webapp; do
  run "mypy ($project)" mypy --cache-dir="/tmp/mypy-cache-$project" \
    --disallow-untyped-defs "$project/src" "$project/tests"
done

run "sqlfluff"     sqlfluff lint --dialect postgres pgvector-db/schema.sql
run "yamllint"     yamllint docker-compose.yml webapp/docs/a11y-ci.yml
run "hadolint"     hadolint \
  cas-to-postgres-importer/Dockerfile \
  global-identity-linker/Dockerfile \
  webapp/Dockerfile \
  pgvector-db/Dockerfile \
  tests/Dockerfile.tests \
  tests/Dockerfile.lint
run "eslint"       eslint .
# The frontend's JSDoc types. No build step: this emits nothing and only
# checks that a DOM lookup is used as the element it actually is, which
# is the class of bug a browser reports as "undefined is not a function"
# and only once that code path runs.
run "tsc"          tsc --noEmit --project webapp/src/frontend/jsconfig.json
run "prettier"     prettier --check .
run "stylelint"    stylelint "webapp/src/frontend/css/*.css"
# Validity only: unclosed tags, bad nesting, an attribute that does not
# belong on an element. Whether the markup is *usable* -- that a control
# has a name, that the tab order is sane, that a reference resolves -- is
# webapp/tests/markup_check.py, driven by test_markup.py. A document can
# be perfectly valid and unusable, which is why both exist. Neither
# should grow into the other.
run "html-validate" html-validate webapp/src/frontend/index.html
run "markdownlint" markdownlint-cli2
run "links"        python /app/tests/check_links.py

# The style guide and the glossary, on every sub-project. No other
# checker enforces prose width, em dashes, glossary terms or docstring
# coverage, so without this they would hold only by review.
for project in global-identity-linker cas-to-postgres-importer webapp; do
  run "style ($project)" python /app/tests/stylecheck.py "$project" \
    --exempt cas/types.py query_agent/schema_context.py
done

# The only workflow-shaped file inside this project. The real workflow
# lives in the repository root's .github/workflows, one directory above
# — outside the mount, and outside the project, which is the same reason
# it does not travel with the code. Check it by hand from the repository
# root:
#
#     docker run --rm -v "$PWD":/w -w /w \
#       duui-video-emotion-visualization/lint:latest \
#     actionlint .github/workflows/duui-video-emotion-visualization.yml
run "actionlint"   actionlint webapp/docs/a11y-ci.yml

printf '\n'
[ "$status" -eq 0 ] && echo "all checks passed" || echo "one or more checks failed"
exit "$status"
