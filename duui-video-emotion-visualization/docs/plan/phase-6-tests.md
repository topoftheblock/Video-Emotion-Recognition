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

**Decided 2026-08-29: drop the testcontainers item.** The database
setup stays exactly as it is — the compose runner brings up
`pgvector-db`, `ensure_test_db.py` creates the test database and applies
the schema, and pytest runs against that. No new dependency, and no
Docker socket in the test container.

What remains is a much smaller question — see §6.5.

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

## 6.3 Redundancy — measured, and none found

The method was: for each candidate, ask what would stop being caught if
it were deleted. Overlap in *input* is not redundancy.

The strongest-looking pair was
`test_contrast.py::test_person_palette_is_read_from_state_js` and
`test_palette.py::test_palette_is_read_from_state_js` — near-identical
bodies asserting the same seven colours from the same file.

They are not redundant. They exercise **two different parsers**:
`contrast_check.load_person_colours` and `cvd_check.load_palette` are
separate implementations, each reading `state.js` for its own checker.
If one broke, only its own test would notice.

That leaves a real observation, recorded rather than acted on: two
helpers in the same suite each parse the palette out of `state.js`. They
could share one parser, since they are in the same sub-project and the
no-shared-files rule does not apply within one. They do not, because
each is documented as independently runnable with nothing but the
standard library, and coupling them would make one script depend on the
other for no gain beyond removing eight lines.

The three `test_*_db_timeout.py` files look alike for the same reason
and are not redundant either: each reads a different settings module.

**Nothing was removed.** No test was found whose failure mode another
test already covers.

## 6.4 Support modules and the linter boundary

The goal is that a reader can tell a helper from a test. Done:

- Each of the three now says in its own header that it is a helper, that
  pytest does not collect it, and which test module drives it.
- The standalone entry point is documented as supported rather than
  accidental, and both reports were run from the documented path to
  confirm they still work.
- The `html-validate` / `markup_check.py` boundary is written into both
  sides — the linter's in `run-lint.sh`, where it is invoked, because
  `.htmlvalidate.json` cannot carry a comment.

**The move to `webapp/tests/support/` was made**, after first being
declined and then reconsidered.

The objection was that it meant updating references across four
documents and a workflow template, three of them commands a person is
told to run, and that stale references have been this project's most
common defect. That reasoning was wrong in one respect: creating a
stale reference is a risk under this phase's control, not an inherent
cost of moving. Declining an approved step to avoid work that can be
done correctly is not a trade-off, it is scope narrowed by the wrong
party.

Done properly: 19 references updated across `accessibility.md`,
`a11y-verification.md`, `axe-baseline.md`, `a11y-baseline/README.md`,
`a11y-ci.yml`, `state.js`, `run-lint.sh` and the three modules
themselves; the path each derives from `__file__` moved one level up;
and both standalone entry points run from their newly documented paths.
A search confirms no reference to the old location survives.

`support/__init__.py` makes it a real package rather than a namespace
one, which mypy needs: without it the modules are reachable under two
names and it refuses to check them.

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

## 6.8 Questions, answered

1. ~~Drop testcontainers?~~ **Dropped** (2026-08-29). The premise it
   rested on was fixed by Phase 4's runner, and adopting it would mean a
   Docker socket in a deliberately non-root container. The database
   setup is unchanged.
2. **Off the supported path: make skips loud** (2026-08-29). They keep
   skipping, but the run says plainly that it was not a full one, so it
   cannot be mistaken for a green suite.
3. **The parser gap: end-to-end first** (2026-08-29). One test drives
   the shipped sample CAS through `run_many()` and asserts what landed,
   covering all eleven parsers and the pipeline. Per-parser tests only
   where that sample cannot reach a branch.

   Measured before deciding: the sample is 581 KB and imports in about a
   second, producing 122 base emotions, 996 emotion scores and 119 face
   detections. Small enough to keep the suite fast, rich enough to
   assert on — so there is no speed trade-off to weigh.
4. **No coverage floor** (2026-08-29). Coverage is measured and recorded
   at the end of the phase, but nothing gates on the number: a floor
   invites tests written to raise a percentage rather than to catch a
   bug.

---

## 6.9 Outcome

Done 2026-08-29. Suite **188 passing**, from 162 at the start of the
phase. All 19 checkers green.

### Coverage

| | Before | After |
| --- | --- | --- |
| **Total** | **48%** | **83%** |
| `importer/pipeline.py` | 16% | 78% |
| `importer/parsers/*` | 22–47% | 82–100% |
| `importer/job_runs.py` | 22% | 90% |
| `identity/job_runs.py` | **0%** | 90% |
| `identity/db.py` | 0% | 100% |
| `importer/cas/typesystem.py` | 25% | 89% |
| `backend/queries/persons.py` | 33% | 100% |

No floor gates on that number, by decision. It is recorded so a later
reader can see whether it moved and ask why.

### What is deliberately still uncovered

| Module | Cover | Why |
| --- | --- | --- |
| `identity/__main__.py` | 0% | An entry point whose body is the real job: connect, recompute the whole corpus, print. Driving it in a test means running the linker, which `test_linking.py` already covers piece by piece. |
| `backend/__main__.py` | 0% | Six statements that call `uvicorn.run`. Testing it would test uvicorn. |
| `query_agent/agent.py` | 26% | The tool-use loop against a language model. Covering it means stubbing the client and asserting against a conversation this project does not control. Worth doing, and larger than the rest of this phase — it is the one gap left open on purpose. |
| `routes/videos.py` | 53% | The uncovered half is the payload route against a video that exists, which needs a populated database. Reachable now that the end-to-end import exists, and worth a follow-up. |

### The sample's one blind spot

The end-to-end test asserts `voice_embeddings == 0`, because the shipped
sample carries none. That branch of `parsers/embedding.py` is the only
parser path the sample cannot reach, and the file says so where the
number is written.

### Deviations from this plan

- **Testcontainers dropped** (§6.1), answered before execution.
- **The support modules were first not moved, then moved** (§6.4). The
  decision to skip it, and why it was reversed, are recorded there.
