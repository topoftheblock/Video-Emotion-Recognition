# Phase 4 — Dependencies, runtime versions, tooling

*Detailed plan for Phase 4. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` plan drafted 2026-08-22, awaiting approval of §4.2 and §4.9.
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

`uvicorn` is declared by the webapp but is **not installed in `.venv`** — it only
exists inside the image. Worth confirming that is intended rather than an
oversight, since it means `uvicorn` is never exercised outside Docker.

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

### Q1 — Python 3.12 → 3.13 or 3.14?

Phase 4 was told to evaluate and recommend. The evaluation is §4.3; the decision
is yours, and **"stay on 3.12, documented" is a valid answer**.

### Q2 — Postgres/pgvector pg16 → pg17 or pg18?

Same. Note the calculus changed in Phase 3: the corpus is now **provably
reproducible** from source CAS in about ten minutes, so a major-version bump no
longer needs `pg_upgrade` — it can be a teardown and re-import, exactly as
Phase 3 did.

### Q3 — Pinning strategy

Three options, in increasing strictness:

1. **Floors only** (today). Reproducible builds: no.
2. **Floors + upper bounds** — `openai>=3.3,<4`. Stops the next major from
   silently changing the program. Cheap, and it fixes the `openai` problem.
3. **Full lock** — a `requirements.lock` per image. Strongest, but Phase 9 owns
   generating it, so this phase would only commit to the strategy.

**Recommendation: 2 now, 3 in Phase 9.** Upper bounds solve the actual observed
risk immediately; the lockfile makes it exact later.

### Q4 — Does the linter gate anything?

CI will run it. Should a **pre-commit hook** run it too? Without one, a red CI is
found after pushing rather than before committing. Cheap to add, mildly annoying
in daily use.

---

## 4.3 The version evaluation (to be filled in during the phase)

Not decided here — this records *how* the question gets answered, so the answer
is evidence rather than preference.

For **Python 3.13/3.14**, per dependency: does a wheel exist for the target
version on `linux/amd64`? The five that matter are `psycopg2-binary`,
`dkpro-cassis` (and its `lxml` pin), `fastapi`, `pydantic`, `openai`. Method:
build a throwaway image `FROM python:3.13-slim`, install each
`requirements.txt`, and run the suite. That answers it properly rather than by
reading changelogs.

For **Postgres**, the questions are whether `pgvector` publishes a `pg17`/`pg18`
tag, whether the vector operators used (`<=>`, `avg()` over `vector`) behave
identically, and whether the schema needs anything. Method: bring up the new tag
against a scratch database, apply `schema.sql`, re-import, compare row counts to
Phase 0 — the same check Phase 3 used.

**Write the outcome down either way.** A documented "stayed on 3.12 because X"
is the deliverable; a silent no-change is not.

---

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

One dev-only `package.json` at the repository root carrying `eslint`,
`prettier`, `stylelint`, `html-validate` and `typescript`. Dev-only is the
load-bearing word: **the frontend keeps its no-build-step deployment**, and the
files served stay byte-identical to the files in `src/`. A Phase 4 exit check
should assert exactly that.

---

## 4.5 The type-checking ratchet

7 of 140 functions carry a return annotation today. Phase 5 adds the rest as it
rewrites each file.

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
| 1 | Declare `lxml` and `starlette`; add `requires-python`; review `requirements-dev.txt` against actual imports | None |
| 2 | Answer Q1/Q2 by experiment (§4.3) and record the outcome | None — throwaway images |
| 3 | Apply the version decisions, if any | Medium if bumping |
| 4 | Apply the pinning strategy from Q3 | Low |
| 5 | Add `ruff` config + `pyproject` tool sections; **do not run the formatter yet** | None |
| 6 | **Run the formatter — its own commit, nothing else in it** | Touches ~182 lines across 74 files |
| 7 | Add the remaining Python-side linters (`mypy` lenient, `sqlfluff`, `hadolint`, `yamllint`, `actionlint`, `markdownlint`, link checker) | Low |
| 8 | Add `package.json` and the JS/CSS/HTML/Markdown tooling; run `prettier` in **its own commit** | Touches most JS and CSS |
| 9 | Write the CI workflow; verify it fires on a change inside the project and stays silent on one outside | Low |
| 10 | Full verification — build all four images, rebuild the corpus, suite at 150/150, frontend byte-identical | — |

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

**Recommendation: run it now.** The churn is the point — it is cheap, mechanical,
and gets a large, boring diff out of the way while it is still separable from the
work that needs reading.

## 4.10 Exit criteria

- [ ] `lxml` and `starlette` declared; `requires-python` set
- [ ] Q1–Q4 answered, outcomes documented — including any "no change"
- [ ] Pinning strategy applied; `openai` no longer permits 1.x
- [ ] Every tool in the §6 roster configured, from repo-root config
- [ ] `cas/types.py` excluded from line-length rules, with the reason recorded
- [ ] Formatter run committed separately from the config that drives it
- [ ] `mypy` running lenient, per-module strictness a one-line change
- [ ] CI workflow in place, `paths:`-filtered on both triggers, with the warning
- [ ] All four images build; corpus rebuild reproduces Phase 0 row counts
- [ ] Suite at 150/150; frontend files byte-identical to source
