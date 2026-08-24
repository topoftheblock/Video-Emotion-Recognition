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
run() {
  name=$1; shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then :; else status=1; printf '!! %s failed\n' "$name"; fi
}

run "ruff format"  ruff format --check .
run "ruff lint"    ruff check .
run "mypy"         mypy --cache-dir=/tmp/mypy-cache cas-to-postgres-importer/src webapp/src global-identity-linker/src
run "sqlfluff"     sqlfluff lint --dialect postgres pgvector-db/schema.sql
run "yamllint"     yamllint docker-compose.yml webapp/docs/a11y-ci.yml
run "hadolint"     hadolint cas-to-postgres-importer/Dockerfile webapp/Dockerfile global-identity-linker/Dockerfile pgvector-db/Dockerfile Dockerfile.tests Dockerfile.lint

printf '\n'
[ "$status" -eq 0 ] && echo "all checks passed" || echo "one or more checks failed"
exit "$status"
