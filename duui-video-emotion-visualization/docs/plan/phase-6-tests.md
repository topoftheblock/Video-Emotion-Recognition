# Phase 6 — Test audit

Branch: `code-cleanup/phase-6`. Written from the code and from measured
coverage, not from the outline in [README.md](README.md) §"Phase 6" —
which turned out to rest on two premises that are no longer true.

---

## 6.1 Two stale premises, checked first

### The suite does not skip silently any more

The outline says: *"Today they skip silently, so a suite can report green
having run a fraction of its assertions"*, and settles on testcontainers
as the fix.

That was true when it was written. It is not true now, because Phase 4
built the container runner:

- `docker compose run --rm tests` — **162 passed, 0 skipped**.
- `run-tests.sh` runs `ensure_test_db.py` first, under `set -e`. With no
  database reachable it aborts before pytest starts, which is what
  happened when D4's verification pointed it at a blackholed host.
- The README already states the property: *"This is the only supported
  way to run the suite... it creates its own empty test database,
  applies the schema, and fails rather than skipping if the database is
  unreachable."*
- CI runs exactly that command.

So a green suite cannot mean "ran a fraction". The skip machinery in the
three `conftest.py` files is unreachable on the supported path; it only
fires when someone runs `pytest` directly, which the README says is not
supported.

**Testcontainers would also not work as assumed.** The tests already run
*inside* a container, and that container has no Docker socket — only the
source bind-mount. Adopting testcontainers means mounting
`/var/run/docker.sock` into a container that deliberately runs as a
non-root user, i.e. giving the test container root-equivalent access to
the host daemon, and reaching the spawned database across a network the
compose project does not manage.

**Proposal: drop the testcontainers item.** What remains is a much
smaller question — see §6.5.

### The Node toolchain now exists

`a11y_browser_check.js` says *"There is no headless-browser toolchain in
this repo (it is Python end to end)"*. Phase 4 added Node, eslint,
prettier and stylelint; Phase 5 added `tsc`. Only the browser download
is still missing.

**The decision stands: the browser sweep stays manual** (confirmed
2026-08-29). What changes is that its stated reason must become true —
see §6.6.

## 6.2 What the coverage measurement actually shows

Run under `coverage` inside the test container, over the supported path.
**Total: 48%** of 1478 statements.

Nothing is uncovered by accident at the top:

| Module | Cover | Reading |
| --- | --- | --- |
| `identity/linking.py` | 99% | The linker's matching logic is genuinely well tested |
| `backend/db.py` | 100% | |
| `backend/queries/videos.py` | 90% | |
| `backend/query_agent/sql_guard.py` | 92% | The safety boundary is tested as one |
| `importer/inputs.py` | 91% | |
| `importer/video_files.py` | 86% | |

And the floor:

| Module | Cover | Missed |
| --- | --- | --- |
| `identity/job_runs.py` | **0%** | 97 |
| `identity/db.py` | **0%** | 5 |
| `identity/__main__.py` | **0%** | 38 |
| `backend/__main__.py` | **0%** | 6 |
| `importer/pipeline.py` | 16% | 97 |
| `importer/job_runs.py` | 22% | 76 |
| `importer/parsers/emotion.py` | 22% | 42 |
| `backend/query_agent/agent.py` | 26% | 37 |
| `backend/queries/persons.py` | 33% | 6 |

### The largest gap, confirmed directly

**No test calls a parser or the pipeline.** Searched: the only match in
any test file is a docstring mentioning `pipeline.py` in passing. The
percentages the eleven `parsers/*` modules show — 22% to 47% — are their
import lines and `def` statements, not their bodies.

So the outline's *"the importer's parsers are only exercised indirectly
through the pipeline"* is generous: the pipeline is not exercised
either. The importer's parsing has no automated test at all. What
protects it today is the manual replace-import that every phase has run
by hand.

### `job_runs.py` is the sharpest instance

The two copies are byte-identical apart from the log prefix. The
importer's reaches 22% by being imported; the linker's reaches **0%**.
The same 97 statements, in the same file twice, and no test drives
either — including the throttle, the heartbeat thread, and the
crash-recovery path that rewrites a stale `running` row.

## 6.3 Redundancy

To be measured, not assumed. The candidates the outline names are the
four accessibility suites (7 + 4 + 16 + 10 tests). They read the same
committed CSS and HTML, so overlap is plausible — but they assert
different properties of it, and overlap in *input* is not redundancy.

**Method:** for each suite, list what would still be caught if it were
deleted. Only a test whose failure mode is already covered by another
test is redundant. Anything that merely re-reads the same file stays.

## 6.4 Support modules and the linter boundary

- `contrast_check.py`, `cvd_check.py` and `markup_check.py` are helper
  libraries that test modules import, not tests. Move them to
  `webapp/tests/support/` so the relationship is visible, and name their
  driving test modules in each header.
- Confirm the standalone entry point (`python3 tests/contrast_check.py`)
  still works after the move, and document it as supported — both
  reports were run during Phase 5 and produce useful output.
- Write the `html-validate` / `markup_check.py` boundary into both:
  the linter owns HTML *validity*, the test suite owns *accessibility
  semantics*.

## 6.5 What remains of the "runnable without Postgres" item

Not testcontainers. The narrower question: **what should happen when
someone runs `pytest` directly, off the supported path?**

Three options, to decide:

1. **Leave it.** Skips are harmless and help ad-hoc runs.
2. **Make skips loud** — a warning summary at the end, so an ad-hoc run
   cannot be mistaken for a full one.
3. **Remove the skip machinery.** The supported path always has a
   database; an unsupported run then fails honestly instead of
   pretending.

## 6.6 Corrections this phase owes

Found while planning, all Phase 5 misses:

1. **Ten `Phase N.N` references survive** in `contrast_check.py`,
   `markup_check.py`, `test_contrast.py` and `a11y_browser_check.js`.
   The Phase 5 commit claimed "the numbers are gone". That was
   overstated: the module docstrings were rewritten, the inline ones
   were not. `docs/accessibility.md` no longer defines any of them.
2. **`a11y_browser_check.js` still claims there is no Node toolchain**
   in its header. Phase 5 corrected the same claim at the foot of the
   file and missed the top.
3. Since the sweep stays manual, its instructions and the baseline it
   points at must be checked by actually following them.

## 6.7 Steps

| # | Step |
| --- | --- |
| 1 | Answer §6.8 |
| 2 | Fix the corrections in §6.6 |
| 3 | Move the support modules; write the linter boundary into both sides |
| 4 | Close the parser and pipeline gap — the largest, and the reason this phase exists |
| 5 | Cover `job_runs.py` once, in a form both copies can carry |
| 6 | Decide and implement §6.5 |
| 7 | Measure redundancy per §6.3; remove only what is genuinely covered elsewhere |
| 8 | Re-measure coverage; record the before and after |
| 9 | Verify: suite green, all checkers green, corpus row counts unchanged |

## 6.8 Open questions

1. **Drop testcontainers?** §6.1 argues the premise is gone and the cost
   is a Docker socket in the test container. Proposed: drop it, and
   answer §6.5 instead.
2. **Which §6.5 option** — leave, loud, or remove?
3. **How far to go on the parser gap?** A fixture CAS through
   `run_many()` covering all eleven parsers is one test that would catch
   most regressions. Per-parser unit tests are eleven times the work for
   a narrower net. Proposed: the end-to-end one first, then per-parser
   only where the pipeline cannot reach a branch.
4. **Is a coverage floor wanted in CI?** A number that cannot fall would
   keep this from decaying. It also has to be maintained honestly.
   Proposed: measure, record, and decide at the end of the phase rather
   than picking a number now.
