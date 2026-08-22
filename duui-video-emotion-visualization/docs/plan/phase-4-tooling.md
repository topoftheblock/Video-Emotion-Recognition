# Phase 4 — Dependencies, runtime versions, tooling

*Detailed plan for Phase 4. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` plan drafted 2026-08-22. Q1–Q4 and §4.9 answered; version
evaluation done — see §4.3.
Branch: `code-cleanup/phase-4`.

## 4.0 What this phase is for

To settle the versions, make the dependency lists honest, and install the tooling
that enforces the style guide mechanically — so that Phase 5 is about meaning and
never about formatting.

**No behavior changes**, except where a version bump is explicitly decided.

---

## 4.1 Findings from the survey

Measured before planning, not assumed.

### Two dependencies are used but not declared

| Package | Imported by | Declared? | Reaches the image via |
| --- | --- | --- | --- |
| `lxml` | `importer/pipeline.py`, `importer/cas/sofas.py`, and two test modules | **No** | `dkpro-cassis` requires `lxml~=6.1.0` |
| `starlette` | `webapp/src/backend/app.py` | **No** | `fastapi` requires `starlette>=0.46.0` |

Both work today by accident. `dkpro-cassis` pins `lxml~=6.1.0`, so a
`dkpro-cassis` release that widened or dropped that pin would break the importer
with no change on our side — and nothing in our requirements would explain why.
The same holds for `starlette` under `fastapi`.

**A direct import is a direct dependency.** Both get declared.

### Installed versions are far ahead of the declared floors

| Package | Floor | Installed | Gap |
| --- | --- | --- | --- |
| `openai` | `>=1.50.0` | **3.3.1** | **two major versions** |
| `pytest` | `>=8.0` | 9.1.1 | one major |
| `fastapi` | `>=0.110` | 0.141.1 | 31 minors |
| `dkpro-cassis` | `>=0.9.0` | 0.11.1 | two minors |
| `pydantic` | `>=2.0` | 2.13.4 | |
| `python-dotenv` | `>=1.0` | 1.2.2 | |
| `psycopg2-binary` | `>=2.9` | 2.9.12 | |

The `openai` floor is the one that matters: `>=1.50.0` permits 1.x, whose client
API differs from the 3.x actually installed and tested against. **A fresh install
resolving to a 1.x would be a different program.** Nothing pins it down.

`uvicorn` is declared by the webapp but is **not installed in `.venv`**.
Investigated 2026-08-22 — **it is not redundant, and the venv is incomplete**:

- It is the image's `CMD`: `uvicorn backend.app:create_app --factory --host
  0.0.0.0 --port 8000`. It is the server that actually runs the webapp.
- `webapp/src/backend/__main__.py:23` does `import uvicorn`, so `python -m
  backend` raises `ImportError` from `.venv` today.

The suite passes without it only because the route tests use
`fastapi.testclient.TestClient`, which drives the ASGI app through `httpx` and
never binds a port. So the venv is fine for tests and broken for running the app
— which nobody noticed, because nobody runs the app outside Docker.

### The interpreter cannot be installed locally

Recorded 2026-08-22: **Python 3.14 is not installable on the development
machine.** Every test run, from this phase onward, happens inside a container.

That is a workflow change, not a footnote — see §4.4b.

### No `requires-python` anywhere

None of the four `pyproject.toml` files declares one. The images say
`python:3.12-slim`; nothing else states a floor, so a contributor on 3.9 gets
confusing failures rather than a clear refusal.

### Scale of what the tooling will touch

| | Count |
| --- | --- |
| Python files | 74 |
| JavaScript | 17 |
| CSS | 12 |
| Markdown | 23 |
| Dockerfile | 4 |
| YAML | 2 |
| HTML / SQL | 1 each |
| **Python lines over 88 columns** | **182** |
| Functions with a return annotation | **7 of 140** |

---

## 4.2 Decisions needed from you

### Q1 — Python version — **decided: 3.14**

All three Dockerfiles move to `python:3.14-slim`. Evidence in §4.3: identical
test results, and 3.12 is already security-only.

`requires-python = ">=3.14"` — **only** 3.14. It is the one version tested, and
claiming support for a version nobody exercises is the kind of unverified claim
the style guide forbids.

### Q2 — Postgres/pgvector — **decided: pg18**

`pgvector/pgvector:pg16` → `pg18`. Evidence in §4.3.

> **This one needs another full rebuild, and it comes first.** A Postgres major
> version has an incompatible on-disk data directory, so the existing volume
> cannot be reused. Decided 2026-08-22: **tear down before making any changes**,
> then rebuild on the new versions — `down -v`, edit, `up --build`, re-import,
> re-link. Same ordering lesson as Phase 3 step 8: the teardown belongs before
> the rename, not after. About ten minutes, and the row counts are the check.

### Q3 — Pinning strategy

Three options, in increasing strictness:

1. **Floors only** (today). Reproducible builds: no.
2. **Floors + upper bounds** — `openai>=3.3,<4`. Stops the next major from
   silently changing the program. Cheap, and it fixes the `openai` problem.
3. **Full lock** — a `requirements.lock` per image. Strongest, but Phase 9 owns
   generating it, so this phase would only commit to the strategy.

**Decided 2026-08-22: floors and ceilings.** Upper bounds solve the observed
`openai` risk immediately; Phase 9 adds the lockfile on top.

### Q4 — Does the linter gate anything? — **decided: a hook for the fast checks**

A pre-commit hook runs **`ruff format --check` and `ruff check` only**. The type
checker, the link checker and everything else stay in CI, where slowness does not
matter. Rationale and mechanics in §4.9b.

The hook must be installable in one documented command, and `--no-verify` stays
available — a gate that cannot be bypassed is one people route around.

---

## 4.3 The version evaluation — done 2026-08-22

Answered by experiment and by checking published support windows, not by
preference.

### Python: the suite passes identically on 3.12, 3.13 and 3.14

Every dependency installed cleanly on each, and the suite was run inside each
image against the real database:

| Image | Interpreter | Result |
| --- | --- | --- |
| `python:3.12-slim` | 3.12.14 | 149 passed, 1 skipped |
| `python:3.13-slim` | 3.13.15 | 149 passed, 1 skipped |
| `python:3.14-slim` | 3.14.7 | 149 passed, 1 skipped |

Identical. Wheels exist on all three for `psycopg2-binary`, `dkpro-cassis`,
`lxml`, `fastapi`, `pydantic` and `openai`, so nothing needed a compiler.

**Support status is what decides it, and it is not close:**

| Version | Status | Released | End of life |
| --- | --- | --- | --- |
| 3.12 | **Security-only** | Oct 2023 | Oct 2028 |
| 3.13 | Bugfix | Oct 2024 | Oct 2029 |
| 3.14 | Bugfix | Oct 2025 | **Oct 2030** |

**The project is already on a version that receives no bug fixes** — only
security patches. That is the finding: staying put is not "no change", it is
choosing an interpreter that has stopped being repaired.

**Recommendation: 3.14.** It tests identically to 3.12, is in active bugfix
support, and buys two more years than staying. 3.13 is equally safe and buys one
year less for the same work, so there is no reason to prefer it.

### Postgres: pg17 and pg18 both work unchanged

A scratch instance of each, with `schema.sql` applied and the vector operations
this project actually uses exercised:

| Image | Server | Schema | `<=>` | `avg(vector)` | pgvector |
| --- | --- | --- | --- | --- | --- |
| `pgvector/pgvector:pg17` | 17.11 | 14 tables, no errors | ok | ok | 0.8.6 |
| `pgvector/pgvector:pg18` | 18.6 | 14 tables, no errors | ok | ok | 0.8.6 |

Same pgvector version on both, so the vector behaviour is identical by
construction.

| Version | Released | Support ends |
| --- | --- | --- |
| 16 (current) | Sep 2023 | Nov 2028 |
| 17 | Sep 2024 | Nov 2029 |
| 18 | Sep 2025 | **Nov 2030** |

**Recommendation: pg18.** It applies the schema unchanged, runs the operators
identically, and is on its sixth minor release. The migration cost that made
this hard is gone: Phase 3 proved the corpus rebuilds from source CAS in about
ten minutes, so this is a teardown and re-import, not a `pg_upgrade`.

## 4.4 Tooling configuration

The roster is [§6 of the plan](README.md#6-the-linter-and-checker-roster). Two
constraints on every config file:

- **It must encode the Phase 1 style guide**: 88 columns for code, 72 for prose,
  US English. Where the guide and a tool's default disagree, the guide wins and
  the config says so.
- **Config lives at the repository root** where the tool allows it, so all four
  sub-projects are covered by one file and cannot drift apart.

### The `cas/types.py` exclusion

`cas/types.py` is 224 lines of UIMA vocabulary, **36 of them over 88 columns**,
almost all inside XML string literals. A formatter reflowing those would corrupt
data to satisfy a line limit written for code.

**Exclude it from line-length enforcement**, and say why in the config. It is a
data file that happens to be `.py`.

### The JS side

One dev-only `package.json` at the **project root**
(`duui-video-emotion-visualization/`), not the git root — the git root belongs to
the container repository and holds unrelated sibling projects. Only the CI
workflow has to live above this directory. It carries `eslint`,
`prettier`, `stylelint`, `html-validate` and `typescript`, and **pins a Node
version** (`engines` plus `.nvmrc`) so CI and any local run cannot drift.
Dev-only is the
load-bearing word: **the frontend keeps its no-build-step deployment**, and the
files served stay byte-identical to the files in `src/`. A Phase 4 exit check
should assert exactly that.

---

## 4.4b Testing moves into Docker

Python 3.14 cannot be installed on the development machine, so **the container is
the only place the suite can run against the real interpreter**. This phase owes
that a first-class path, because a test command nobody can type is a test command
nobody runs.

What has to exist by the end of this phase:

- **One short command that runs the whole suite** against `python:3.14-slim`,
  joined to the compose network so the database-backed tests actually run rather
  than skip. Today that is a nine-line `docker run` invocation — unusable as a
  habit. A compose service (`docker compose run --rm tests`) fits the project's
  existing idiom better than a shell script, and inherits the network and
  environment for free.
- **The same command in CI**, so local and CI cannot diverge.
- A loud failure when the database is unreachable, rather than 29 quiet skips.
  D13 showed how invisible that is; Phase 6 fixes it properly with
  testcontainers, but the runner should not hide it in the meantime.

### `.venv` is deleted

**Decided 2026-08-22.** It is Python 3.12.3, will not match the runtime, cannot
run the app (no `uvicorn`, §4.1), and a green run from it would mean nothing.
Keeping it as an editor convenience was considered and rejected: the risk is not
the directory, it is the belief that results from it count.

It is gitignored, so removing it is a local action plus a documentation change:
**`README.md:46` currently tells the reader to run `.venv/bin/python -m pytest`**
and must point at the Docker service instead. `docs/plan/phase-0-baseline.md`
keeps its references — that file is a record of what was true then, not
instructions.

The consequence to plan around: **ruff, for the pre-commit hook, then has no
Python to live in.** It is a standalone binary, so install it via `pipx`, the
system package manager, or `uv tool`, configured with `target-version = "py314"`
so it judges the code by the runtime rather than by whatever interpreter it
happens to run under. That instruction has to be written down, or the hook is
uninstallable.

### The test service creates its own database

D13 was caused by nothing recreating `duui_baseline_test` after a rebuild. The
runner should close that hole rather than leave it for Phase 6: **the service
ensures the empty test database exists and has `schema.sql` applied before it
runs `pytest`.**

Two things follow. A rebuild stops silently degrading the suite from 150 passed
to 121 passed and 29 skipped, and the green baseline stops depending on a
manual step nobody has written down.

## 4.5 The type-checking ratchet

7 of 140 functions carry a return annotation today. Phase 5 adds the rest as it
rewrites each file.

`mypy` is the checker (decided 2026-08-22, over `pyright`): it is the reference
implementation, its per-module strictness is exactly what the ratchet needs, and
it does not pull Node into the Python toolchain.

Run it with `--python-version 3.14` so it checks against the target semantics
even when invoked from an older interpreter.

So this phase installs `mypy` **lenient everywhere**, and Phase 5 tightens each
sub-project as it finishes it, per the ratchet in [§7](README.md#7-decisions-log).
What Phase 4 owes: a config where per-module strictness is a one-line change, so
Phase 5 does not have to design it mid-rewrite.

---

## 4.6 The CI workflow

At `<git-root>/.github/workflows/`, since that is the only place Actions reads
from — **outside this project directory**, which is the wrinkle.

- `paths:` filters on `duui-video-emotion-visualization/**`, on **both**
  triggers. The sibling `ci.yml` filters only `push`, so its `pull_request`
  runs on every PR in the repository; do not copy that.
- No database, no application dependencies. Lint and type-check only.
- Header comment carries the **"moving this project breaks the CI"** warning
  from §7 — it does not travel with the project and fails silently when left
  behind.

---

## 4.7 Steps, in order

Each step is one commit; suite green before each.

| # | Step | Risk |
| --- | --- | --- |
| 0a | **Add the Docker test service first** (§4.4b), on the current 3.12 images, and confirm it reproduces 150/150 | None — this is the safety net for everything after |
| 0b | **`docker compose down -v`** — only once 0a passes, since pg18 cannot reuse the pg16 volume (§4.2 Q2) | Destroys the corpus, by design |
| 1 | Declare `lxml`, `starlette` and `uvicorn`; set `requires-python = ">=3.14"`; review `requirements-dev.txt` against actual imports | None |
| 2 | ~~Answer Q1/Q2 by experiment~~ — **done**, §4.3 | — |
| 3 | Apply the bumps: `python:3.14-slim` ×3, `pgvector/pgvector:pg18`; then `up --build`, re-import, re-link, compare row counts | Medium |
| 3b | Delete `.venv`; repoint `README.md:46` at the test service; document how to install `ruff` standalone | Low |
| 4 | Apply the pinning strategy from Q3 | Low |
| 5 | Add `ruff` config + `pyproject` tool sections; **do not run the formatter yet** | None |
| 6 | **Run the formatter — its own commit, nothing else in it** | Touches ~182 lines across 74 files |
| 7 | Add the remaining Python-side linters (`mypy` lenient, `sqlfluff`, `hadolint`, `yamllint`, `actionlint`, `markdownlint`, link checker) | Low |
| 8 | Add `package.json` and the JS/CSS/HTML/Markdown tooling; run `prettier` in **its own commit** | Touches most JS and CSS |
| 9 | Write the CI workflow; verify it fires on a change inside the project and stays silent on one outside | Low |
| 10 | Add the pre-commit hook for `ruff format --check` and `ruff check` (§4.9b) | Low |
| 11 | Full verification — all four images build, corpus row counts match Phase 0, suite at 150/150 **via the Docker runner**, frontend byte-identical | — |

**Steps 6 and 8 are the ones to keep isolated.** A formatting run mixed with a
config change produces a diff nobody can review, and this phase's whole purpose
is to make Phase 5 reviewable.

---

## 4.8 The risk worth stating

This phase installs tools that will rewrite **every file in the repository**.

If a config disagrees with the style guide, **the tooling wins silently** — and
Phase 5 then writes 50 files against the wrong rules. The guard is step 5 and
step 6 being separate commits: configure, read the config against
`docs/documentation-style.md` §8, *then* run.

There is a precedent from Phase 3 worth repeating here: a warning in prose does
not protect against a sequence that contradicts it. The step order above is the
protection.

---

## 4.9 Open question: should the formatter run at all in this phase?

Running `ruff format` reflows 182 lines across 74 files — files that **Phase 5
is about to rewrite by hand anyway**.

- **Run it now** (as planned): Phase 5 never argues about formatting, and every
  file it opens is already conformant.
- **Defer to Phase 5**: no throwaway churn, but Phase 5 does formatting and
  meaning in the same commits, which is exactly what makes a diff unreviewable.

**Decided 2026-08-22: run it in this phase, in its own commit** — steps 6 and 8.

## 4.9b Q4, explained: what a pre-commit hook would mean

A **pre-commit hook** is a script git runs on your machine every time you type
`git commit`. If it exits non-zero, the commit does not happen.

The choice is *when* you find out a file breaks the rules:

| | Where it runs | You find out | If it fails |
| --- | --- | --- | --- |
| **CI only** | GitHub, after `git push` | Minutes later, in a browser | The commit exists; you fix it in a follow-up commit |
| **CI + hook** | Your machine, at `git commit` | Immediately, in the terminal | The commit never happens; you fix and retry |

What it costs: every commit gets slower by however long the linters take —
seconds here — and it occasionally blocks a commit you wanted to make anyway,
mid-thought. It can always be bypassed with `git commit --no-verify`, which
matters because a hook you cannot override becomes a hook people work around.

It is also **local-only**: hooks are not committed by git, so each clone has to
install it. In practice that means a `make hooks` or a line in the README.

**My recommendation: yes, but only for the fast, non-negotiable checks** —
formatting and lint. Leave the type checker and the link checker to CI, since
those are slower and their failures are less clear-cut. That way a commit stays
fast and the hook never becomes the thing you routinely skip.

There is a real argument for CI-only: this is a single-developer project, so the
hook mostly protects you from yourself, and a red CI on your own branch costs
little. If the slowdown would annoy you, CI-only is defensible.

## 4.10 Exit criteria

- [ ] `lxml`, `starlette` and `uvicorn` declared; `requires-python = ">=3.14"`
- [ ] Python 3.14 and pgvector pg18 in place; corpus rebuilt and verified
- [ ] A short Docker command runs the whole suite, documented as the only
      supported way; `.venv`'s status decided and written down
- [ ] Pre-commit hook installs in one command and is bypassable
- [ ] Q1–Q4 answered, outcomes documented — including any "no change"
- [ ] Pinning strategy applied; `openai` no longer permits 1.x
- [ ] Every tool in the §6 roster configured, from repo-root config
- [ ] `cas/types.py` excluded from line-length rules, with the reason recorded
- [ ] Formatter run committed separately from the config that drives it
- [ ] `mypy` running lenient, per-module strictness a one-line change
- [ ] CI workflow in place, `paths:`-filtered on both triggers, with the warning
- [ ] All four images build; corpus rebuild reproduces Phase 0 row counts
- [ ] Suite at 150/150; frontend files byte-identical to source
