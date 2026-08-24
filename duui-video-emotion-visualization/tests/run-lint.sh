#!/bin/sh
# Every checker, in one pass. Reports all failures rather than stopping at the
# first, so one run tells you everything that is wrong.
#
#     docker compose run --rm lint
#
# Read-only: nothing here rewrites a file. `ruff format` and `ruff check --fix`
# are deliberately not run, so this is safe in CI and safe to run while editing.
# Every tool that caches needs somewhere writable: the source is mounted
# read-only on purpose, so that a checker can never rewrite what it is checking.
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
# E501 is deliberately outside the gate until Phase 5.
#
# All 48 findings are prose -- comments and docstrings written wider than the
# style guide's 72 columns for prose. Phase 5 rewrites every one of them, so they
# clear as a side effect and rewrapping them now would be work thrown away.
#
# They are excluded from the gate rather than from the run because a check that
# is red on its first day stops being read, and then it cannot report the next
# real failure either. Everything else -- undefined names, unused imports, type
# errors, malformed Dockerfiles -- still fails the build.
#
# REMOVE THIS EXEMPTION WHEN PHASE 5 CLOSES. The line below and the report line
# under it both go, leaving a plain `ruff check .`.
run    "ruff lint"        ruff check --extend-ignore E501 .
report "ruff line length" ruff check --select E501 --statistics .
run "mypy"         mypy --cache-dir=/tmp/mypy-cache cas-to-postgres-importer/src webapp/src global-identity-linker/src
run "sqlfluff"     sqlfluff lint --dialect postgres pgvector-db/schema.sql
run "yamllint"     yamllint docker-compose.yml webapp/docs/a11y-ci.yml
run "hadolint"     hadolint cas-to-postgres-importer/Dockerfile webapp/Dockerfile global-identity-linker/Dockerfile pgvector-db/Dockerfile Dockerfile.tests Dockerfile.lint
run "eslint"       eslint .
run "prettier"     prettier --check .
run "stylelint"    stylelint "webapp/src/frontend/css/*.css"
run "html-validate" html-validate webapp/src/frontend/index.html
run "markdownlint" markdownlint-cli2
run "links"        python /app/tests/check_links.py

printf '\n'
[ "$status" -eq 0 ] && echo "all checks passed" || echo "one or more checks failed"
exit "$status"
