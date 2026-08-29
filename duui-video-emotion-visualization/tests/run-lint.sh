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
# One mypy invocation per sub-project, because each owns a `tests/conftest.py`
# and mypy identifies a module by its name: pass all three paths at once and it
# sees three different files claiming to be `conftest`, then stops on the
# duplicate rather than checking anything. The sub-projects do not share files by
# design, so they are checked the way they are built -- separately.

# Finished sub-projects. Phase 5 has rewritten these, so they are held to the
# full standard: `tests` is checked alongside `src`, and every function must
# carry annotations. Move a name up here when its rewrite lands -- that is the
# ratchet, and it is why this list is the one place that records what is done.
for project in global-identity-linker cas-to-postgres-importer; do
  run "mypy ($project)" mypy --cache-dir="/tmp/mypy-cache-$project" \
    --disallow-untyped-defs "$project/src" "$project/tests"
done

# Not yet rewritten. `src` only, and no strictness: these still hold unannotated
# functions by the hundred, and reporting work that has not been scheduled yet
# just makes a red check that stops being read. Their tests join the run at the
# same moment their annotations do.
for project in webapp; do
  run "mypy ($project)" mypy --cache-dir="/tmp/mypy-cache-$project" "$project/src"
done

run "sqlfluff"     sqlfluff lint --dialect postgres pgvector-db/schema.sql
run "yamllint"     yamllint docker-compose.yml webapp/docs/a11y-ci.yml
run "hadolint"     hadolint cas-to-postgres-importer/Dockerfile webapp/Dockerfile global-identity-linker/Dockerfile pgvector-db/Dockerfile tests/Dockerfile.tests tests/Dockerfile.lint
run "eslint"       eslint .
run "prettier"     prettier --check .
run "stylelint"    stylelint "webapp/src/frontend/css/*.css"
run "html-validate" html-validate webapp/src/frontend/index.html
run "markdownlint" markdownlint-cli2
run "links"        python /app/tests/check_links.py

# The style guide and the glossary, on the sub-projects Phase 5 has
# finished. Same list as the mypy ratchet above, and it moves with it:
# no other checker enforces prose width, em dashes, glossary terms or
# docstring coverage, so without this they hold only by review.
for project in global-identity-linker cas-to-postgres-importer; do
  run "style ($project)" python /app/tests/stylecheck.py "$project" \
    --exempt cas/types.py
done
# Reported, not gated, until Phase 5 rewrites it.
report "style (webapp)" python /app/tests/stylecheck.py webapp

# The only workflow-shaped file inside this project. The real workflow lives in
# the repository root's .github/workflows, one directory above -- outside the
# mount, and outside the project, which is the same reason it does not travel
# with the code. Check it by hand from the repository root:
#
#     docker run --rm -v "$PWD":/w -w /w \
#       duui-video-emotion-visualization/lint:latest \
#       actionlint .github/workflows/duui-video-emotion-visualization.yml
run "actionlint"   actionlint webapp/docs/a11y-ci.yml

printf '\n'
[ "$status" -eq 0 ] && echo "all checks passed" || echo "one or more checks failed"
exit "$status"
