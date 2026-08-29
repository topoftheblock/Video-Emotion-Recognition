# Phase 5 — In-file documentation rewrite

*Detailed plan for Phase 5. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` plan complete, 2026-08-22. All eight questions answered.
Branch: `code-cleanup/phase-5`.

## 5.0 What this phase is for

Every comment and docstring in the project, rewritten once, against a settled
structure and a settled style guide.

This is the phase the whole plan exists to reach, and **the one most able to do
harm**. Every other phase either moved things or added machinery; a wrong move
was caught by a test, a linter, or a rebuild. Nothing catches a confident
sentence that is false. It will be read, believed, and acted on — which is
exactly how this codebase's comments became untrustworthy in the first place.

---

## 5.1 The rules

**Read these before touching a file, not after.** They are not style preferences;
they are what separates this pass from the one that created the problem.

### The three overriding rules

From [`docs/documentation-style.md`](../documentation-style.md), which is
binding:

> **1. Write only what you can verify.**
> Every statement must be checkable against the code, the database, the schema,
> a test, or an authoritative external source. If it cannot be checked, it does
> not go in.
>
> **2. The existing comments are not evidence.**
> They are legacy text: some accurate, some outdated, some simply wrong, with
> nothing to tell them apart. A comment is *never* a source — not for what the
> code does, and **not for why it does it**. When an existing comment states a
> reason, you may not carry that reason forward merely because it is already
> written down.
>
> **3. Never invent a rationale, and never assume one.**
> If you cannot establish *why*, write what it does and say plainly that the
> reason is not recorded. **If the reason matters and you cannot determine it,
> stop and ask.**

**Rule 2 is the expensive one, and the one that will be tempting to soften.**
There are **683 comment lines** across the three Python sub-projects. Every one
of them is a plausible-sounding sentence that is already written, already fits,
and would cost nothing to keep. Keeping one because it reads well is the single
most likely way this phase fails.

Three times already in this plan a comment was carried forward or invented and
turned out wrong — the "ArcFace-style" threshold that the `models` table
contradicted, the `person 1` collision the corpus does not contain, and two
rationales invented in a 60-line file *while the guide was being written*. The
rate is not low.

### The mechanical rules

| Rule | Test |
| --- | --- |
| **Comment budget** | Could a competent reader work this out from the code in under ten seconds? If yes, delete it. |
| **8-line rule** | A comment longer than 8 lines belongs in `docs/`, leaving a summary and a link. Docstrings are exempt from the *count*, not the *principle*: length is fine for describing what a module owns, not for arguing a design decision. |
| **History goes, reasons stay** | Delete what the code used to do, what was tried first, which bug prompted it. Keep the constraint that still binds. |
| **Docstrings** | Google style, summary on the first line, imperative, one sentence. No types in the docstring — the annotation carries them. |
| **No corpus figures** | Row counts, id ranges and per-table totals describe one database on one day, not the software. Write the property; leave the measurement in the phase record. Rule 4 of the style guide. |
| **Glossary** | [`docs/glossary.md`](../glossary.md) is binding on comments, docstrings **and user-facing strings**. |
| **US English**, 88 columns for code, 72 for prose | |

### The rules from §5 of the plan overview

- **A found bug stops the work.** Note it; implement the fix only if it is clear
  and sensible; otherwise **interrupt and ask**. This phase reads every line of
  the project, so it will find things. Two of the three defects found so far in
  this cleanup were found by reading, not by running.
- **Duplicated code carries duplicated documentation.** `job_runs.py` exists
  twice and currently differs by **25 lines of prose over identical behaviour**.
  After this phase the two must say the same thing in the same words, differing
  only where behaviour differs — and saying so where it does. **Diff the pair as
  a verification step, not just as a starting point.**
- **No AI attribution**, and never describe the old comments as AI-written in
  any committed file. *Legacy*, *unverified*, *outdated*.
- Commit messages start with the `Phase 5:` prefix.

---

## 5.2 The measured scale

| | Count |
| --- | --- |
| Python files — `src/` | 51 |
| Python files — sub-project `tests/` | 23 |
| Python files — the runners in `tests/` | 2 |
| JavaScript | 17 |
| CSS | 12 |
| HTML / SQL | 1 / 1 |
| Dockerfiles | 6 |
| Config — compose, 4 `pyproject.toml`, 4 requirements, `.env.example`, 4 `.dockerignore` | 14 |
| **Total files** | **~127** |

| Work item | Now | Target |
| --- | --- | --- |
| Functions with a return annotation — `src` | **7 of 140** | 140 |
| Functions in `tests` — also in scope (Q2) | 191 | 191 |
| `mypy --disallow-untyped-defs` errors | **358** — 134 in `src`, 224 in `tests` | 0 |
| JS files with `// @ts-check` | **1 of 16** | 16 |
| `tsc --checkJs` errors | **40** | 0 |
| Comment lines to judge | **683** | — |
| `E501` (prose past 88 columns) | **48** | 0 |
| `viewer` in prose | **47** | 0 |
| `job_runs.py` prose divergence | **25 lines** | 0 |

---

## 5.3 What the fact ledger hands over

Seven entries from [phase-2-ledger.md](phase-2-ledger.md) are assigned here.
These are the corrections this phase must make — not optional polish.

| | What |
| --- | --- |
| **D4** | No `connect_timeout` in any application code. `create_app()` hangs at startup against a blackholed host. **A behaviour change — see §5.8 Q1.** |
| **D5** | `pipeline.py` prints `Loading CAS data from …` *before* deciding to skip the file. A user-facing string that describes work not done. |
| **D7** | `linking.py` justifies the composite key with a collision the corpus does not contain. The reason is right; state the verifiable version — 4,762 colliding `emotion_id` values, and `emotion_id` 16621 in videos 3 and 6. |
| **D8** | `--on-existing replace` does not preserve `video_id`. Undocumented; document it. |
| **D10** | `accessibility.md` says "viewer" twice and predates the style guide. Content is correct; terminology and style get a pass. |
| **D12** | **17 stale references across 15 files** to documentation that moved. Each must be repointed at whichever `docs/` page now owns the subject. |
| **D15** | Three user-facing surfaces give three different project names. **Needs a decision — §5.8 Q5.** |

---

## 5.4 Order, and the strictness ratchet

Smallest first, so the style guide is shaken out on cheap files:

**`pgvector-db` → `global-identity-linker` → `cas-to-postgres-importer` →
`webapp`** (backend, then frontend JS, then CSS).

`pgvector-db` has no Python at all — `schema.sql`, a `Dockerfile`, a
`.dockerignore`. That makes it a genuine first checkpoint: small enough to
finish quickly, real enough to test the guide.

### The ratchet

As each sub-project is finished, tighten `mypy` on it immediately rather than
leaving everything lenient and flipping one switch at the end. A finished
sub-project is then held to the strict setting and **cannot regress while the
next one is in progress**. By the end, strict is already on everywhere and there
is no cliff.

Step sizes, `src` plus `tests` (Q2): **44**, then **137**, then **177**.

**Where the ratchet lives — corrected in execution.** The plan originally put it
in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = ["identity.*"]
disallow_untyped_defs = true
```

That does not work, and the reason is worth keeping. The override matches on
module name, and it has to cover a sub-project's `tests` as well as its `src`
(Q2) — but a test module has no package to qualify it. All three sub-projects
own a plain `conftest`, so `module = ["conftest", "test_*"]` matches all three
at once and turns strictness on for two sub-projects that have not been
rewritten yet. Tried, and it did exactly that: 7 errors across the importer's
and the webapp's conftests.

So the ratchet lives in `tests/run-lint.sh` instead, as a **list of finished
sub-projects** that get `--disallow-untyped-defs`, with the rest checked
leniently. Moving a name between the two lists is the whole operation, and the
list is the record of what is done. `pyproject.toml` points at it.

Two things follow from the same constraint:

- `mypy` runs **once per sub-project**, because those three `conftest` modules
  collide as duplicates in a single invocation and it stops rather than checking
  anything. `run-lint.sh` needed this before the ratchet could start.
- A sub-project's **`tests` join its `mypy` run when its rewrite lands**, not
  before — the same ratchet, applied to coverage as well as strictness. Adding
  all the tests up front makes the check red on work that is not scheduled yet,
  which is how a check stops being read.

**Carried forward:** `webapp/tests/conftest.py:40` assigns `None` to `DB_CONFIG`
in an `except ImportError` fallback, where `backend.config.DB_CONFIG` is
`dict[str, str]`. Not a runtime fault — every use is guarded by `is None` — but
it needs `DB_CONFIG: dict[str, str] | None` when the webapp's turn comes. Found
by pointing `mypy` at the tests, not by any test run.

### The checkpoint

**After `global-identity-linker` — the first sub-project with code — stop.**
Review the result against the style guide, amend the guide if it did not survive
contact, *then* continue. The guide has been applied to exactly two files so far
(`identity/config.py` and `identity/db.py`, in Phase 1) and it changed five times
during that exercise.

### What the checkpoint found

Applied to `global-identity-linker` and checked against the guide afterwards.
The guide held; the *application* of it did not, in four ways.

1. **Prose width was ignored, at scale.** 212 comment and docstring lines were
   wrapped at 88 instead of the guide's 72 — including files rewritten in the
   same session that quoted the rule. `db.py`, rewritten in Phase 1 and used to
   validate the guide, sits at a maximum of 69, so the rule is workable; it was
   simply not applied. Nothing enforces it: `E501` fires at 88, and only for
   Python. **Every later sub-project needs this checked explicitly**, since no
   linter will say a word. Guide sharpened to say so.

2. **Em dashes were written `--`, 21 times.** The guide says `—`; `--` is the
   legacy style the rewrite is supposed to remove. Two of the conversions land
   in user-facing strings — a `pytest.skip` message, and the
   `'interrupted — superseded by a later run'` text written into
   `job_runs.message` — so this one is visible in the product, not only in the
   source. Guide amended to say the rule covers user-facing strings too.

3. **Section banners were inconsistent and partly malformed.** They existed as
   `# -- name ---` (two dashes, lowercase) against the guide's
   `# --- Name ---`, and widths ran 73 and 74 in the same file. Now uniformly
   74. Worth knowing that a naive ` -- ` → ` — ` substitution *eats these
   banners*, and that `(\s*)` in a multiline pattern swallows the preceding
   newline; both happened here and both were caught by `ruff format`, not by
   reading.

4. **Twelve `# noqa: BLE001` directives suppress a rule that is not
   enabled.** `select = ["E", "F", "I"]` — `BLE` is not in it, so every one of
   them is dead, and each implies a rule the project does not run. Verified by
   deleting one and watching `ruff` still pass. The nine in the linker and its
   `job_runs` twin are gone, reasons kept as ordinary comments. **Three
   remain** — `cas-to-postgres-importer/src/importer/video_files.py`,
   `.../pipeline.py`, and `webapp/src/backend/queries/jobs.py` — for those
   sub-projects' turns.

**Method note.** Rewrapping prose mechanically is not safe on its own. What
caught the damage here was comparing the *word stream* of every comment and
docstring before and after, so a rewrap shows as zero edits and any change of
wording stands out, plus an AST comparison with docstrings stripped to prove no
executable code moved. Both are worth repeating on the two larger sub-projects,
where hand-reading a diff of this size is not realistic. Note the trap: compare
against `HEAD`, not against a mid-session backup, or edits made before the
backup go unchecked — a whole-file `--` substitution can reach inside a string
literal, and only the `HEAD` comparison would show it.

### `cas-to-postgres-importer`, and what checking it mechanically found

The checkpoint's first finding — that nothing enforces the guide, so it
holds only by review — was acted on before this sub-project was touched:
`tests/stylecheck.py` now checks prose width, em dashes, banner form,
glossary terms in prose **and in identifiers**, dead `noqa`, missing
docstrings and corpus references, and `run-lint.sh` gates on it for the
finished sub-projects. It reported 373 findings on the importer at the
start and 0 at the end.

Two things about running it are worth keeping:

- **It must run on the project's own interpreter.** The host's Python is
  older, and `except A, B:` (PEP 758) is a syntax error there. The first
  run reported two files as broken that are perfectly valid, and a
  checker that cannot parse a file silently checks nothing at all.
- **`cas/types.py` shadows the standard library's `types`.** Any script
  run with that directory as the working directory fails on `import
  pathlib`. Harmless to the package, which imports relatively, but it
  cost one confusing failure.

What it found that review would not have:

1. **`python -m main` in seven places.** The entry point has been
   `python -m importer` since Phase 3. Three source files told the user
   to run a command that does not exist.
2. **Two more stale references**: `views.py` pointed at
   `config.IGNORED_ABSENT_TYPES`, which moved to `cas/types.py` in Phase
   3; `pipeline.py` cited a README section — "Docker architecture" —
   that does not exist. `tests/conftest.py` named `src.config` for what
   is `importer.config`.
3. **Rule 4 violations in the tests.** `test_identity.py` carried exact
   corpus figures. The *reason* those tests exist is essential and was
   kept; the counts are gone.
4. **Glossary violations in identifiers, not prose.** The linker's
   public `clear_global_identities` and `recompute_global_identities`
   use "identity" as a noun for the entity, which the glossary forbids.
   Renamed to `clear_global_persons` and `recompute_global_persons`
   across every call site. The checker now reads identifiers for this
   reason — it is the class of violation a prose-only check cannot see.
5. **28 mypy errors, from the annotations themselves.** Two kinds, both
   mine: annotating `source_dir: str` where the code has always accepted
   a `Path` and the tests pass one, and annotating UIMA feature
   structures as `object` when they are dynamically attributed and
   `Any` is the honest type.

**Re-checking the linker with the same tool found 16 findings in a
sub-project already reviewed and committed** — missing docstrings on
every test function, plus the identifier violations above. Fixed. That
is the clearest argument for the checker: the same guide, applied by
hand and then by tool, gave different answers.

### Verifying the importer

The AST-comparison method from the checkpoint does not transfer here.
It proved the linker's rewrite touched no code, but this rewrite
legitimately changes code: it adds annotations and imports, wraps eight
`INSERT` statements, and renames functions. Stripping docstrings *and*
annotations still reported 26 files, all of them true.

Two checks did carry the weight:

- **Every SQL literal, whitespace-normalized, against `HEAD`.** Wrapping
  a statement must not change it. Zero of the 46 statements differ.
- **A full delete-and-reimport.** `--on-existing replace` deletes a
  video's whole subtree and re-parses the CAS, so it exercises every
  parser. All twelve table counts came back identical, as did the split
  across all three emotion modalities, both segment kinds and both
  presence modalities.

One test failed during the rewrite, correctly: it pinned the exact
wording of a user-facing warning that the em-dash rule changed. It now
asserts on what the message must *convey* — the filename, and where to
put the file — rather than on its phrasing.

**A method warning.** A line-numbered `sed` was used to shorten one
docstring after other edits had shifted the file, and it overwrote a
`def` line instead. The suite still passed, because the function had
silently stopped being collected; `ruff format` caught it. Address
edits by matching their text, never by line number.

---

## 5.5 Steps

One sub-project per group of commits; suite and lint green before each.

| # | Step |
| --- | --- |
| 1 | Answer §5.8 |
| 2 | `pgvector-db`: `schema.sql`, `Dockerfile`, `.dockerignore` |
| 3 | `global-identity-linker`: 5 src modules, 3 test modules, config files |
| 4 | **Checkpoint** — review against the guide, amend it, record what changed |
| 5 | Tighten `mypy` on `identity.*` |
| 6 | `cas-to-postgres-importer`: 15 src modules (11 parsers), 6 test modules |
| 7 | Tighten `mypy` on `importer.*` |
| 8 | `webapp` backend: 14 modules, 15 test modules |
| 9 | Tighten `mypy` on `backend.*` |
| 10 | `webapp` frontend: 16 JS modules — JSDoc, `// @ts-check`, and `tsc` in the lint service |
| 11 | `webapp` frontend: 12 stylesheets, `index.html` |
| 12 | Project-level: `docker-compose.yml`, `pyproject.toml` × 4, requirements × 4, `.env.example`, the 6 Dockerfiles, the 2 runner scripts |
| 13 | **Remove the E501 exemption** from `tests/run-lint.sh` and the pre-commit hook; confirm the gate is clean with it enforced |
| 14 | Full verification |

---

## 5.6 What the webapp found, and what closed the phase

### The webapp

The largest sub-project, and the one where "the existing comments are
not evidence" paid for itself most often. Six claims were wrong:

1. **`config.py` said the webapp only reads the database.** It also
   creates `job_runs` at startup, best-effort, for a database that
   predates that table.
2. **`queries/jobs.py` justified a 30-second staleness window** by
   saying the writers heartbeat "about once a second", making it
   "generous by an order of magnitude". The background heartbeat is
   every five seconds; one second is the throttle on progress writes,
   which is a different thing. Thirty seconds is six missed beats.
3. **`agent.py` explained that a provider's reasoning field is
   ignored.** Nothing in the code touches that field, and the claim is
   about an external service that cannot be checked from here.
4. **`schema_context.py` cited `docs/data_schema_with_types.md`.** That
   path has never existed — Phase 2 found this and it was never fixed.
   `docs/database.md` and `cas/types.py` pointed at the old location too.
5. **The webapp's conftest said its tests need no rollback fixture
   because the webapp only reads.** They write, then delete. The real
   reason is that the query functions under test open their own
   connections, so uncommitted rows would be invisible to them.
6. **`a11y_browser_check.js` said wiring the browser sweep into CI would
   mean adding a JavaScript toolchain "to a repo that has neither".**
   Phase 4 added the toolchain. Half that reason had been false since.

Plus a whole *class* of dangling reference: eight comments cite "Phase
N.N of docs/accessibility.md", and that file says outright that the
phase-by-phase plan is gone. History goes, reasons stay.

**Recorded, not changed:** the `run_sql` tool description promises the
model a "total row count" that the implementation never returns — it
sends back only the rows shown and a more-rows flag. Changing prompt
text changes agent behaviour, which Q3 puts outside this phase.

### The frontend

40 pre-existing `tsc` errors, almost all one mistake repeated: a DOM
lookup typed as a bare element, then used as a video, an input or a
canvas. Twenty-two cleared from `lib/dom.js` alone. `tsc --noEmit` now
runs in the lint suite. Two were real looseness rather than a missing
type: a number assigned to `input.value`, and `input.value` divided by a
number — JavaScript coerces both, so they worked.

### Mistakes worth keeping

Every one came from a mechanical pass applied where the file's syntax
uses the same characters as prose:

- The comment rewrapper folded `#!/bin/sh` into the paragraph below it,
  and all three shell scripts stopped being executable.
- The em-dash substitution rewrote `--` inside the pre-commit hook's
  `git diff --cached ... -- <paths>`, where it is the argument
  separator. git refused the next commit outright.
- The banner conversion turned the *first prose line* of two stylesheets
  into a banner name, because both open with a rule of dashes and then a
  paragraph rather than a title.
- The HTML rewrapper joined paragraphs, and an earlier substitution
  deleted an em dash sitting at a line break instead of converting it —
  silently changing what one sentence said.
- A line-numbered `sed` overwrote a `def` line after other edits had
  shifted the file. The suite still passed, because the function had
  quietly stopped being collected.

**The rule this yields:** never run a prose transformation over a whole
file. Restrict it to comment and docstring ranges, and check afterwards
that the non-prose parts are byte-identical. Every one of these was
caught in under a minute by a gate — `ruff format`, git itself, the
style checker — and none by re-reading the diff.

### Closing the phase

The E501 exemption is gone from both `tests/run-lint.sh` and the
pre-commit hook, as its removal marker instructed; `ruff check .` is now
plain, and was verified to fail on an over-long line. All three
sub-projects are in the strict `mypy` list with their tests, and all
three are gated on the style checker.

---

## 5.6 The risk, stated plainly

**Nothing in the toolchain can catch a false sentence.**

The suite proves behaviour, `mypy` proves types, `ruff` proves syntax, the link
checker proves paths resolve. **None of them reads a comment for truth.** A
docstring claiming the opposite of what the function does passes every one of
the thirteen checkers built in Phase 4.

So the verification for this phase is different in kind from every phase before
it. It cannot be "the suite is green". It has to be:

- **Every factual claim traced to something.** A schema column, a test that
  asserts it, a query against the corpus, an upstream document.
- **Uncertainty written down as uncertainty**, in the file, where the next reader
  meets it.
- **The `job_runs.py` pair diffed**, because that one has a mechanical check.
- **Spot-read as a stranger**, at the end: open five files at random and ask
  whether a newcomer could act on what they say.

---

## 5.7 What "done" looks like for one file

So the standard is concrete rather than aspirational:

1. Module docstring: what it owns, and what it deliberately does not.
2. Every function: Google-style docstring, full annotations, no types in prose.
3. Every surviving comment answers a question the code cannot.
4. Every claim in it is verifiable, or marked as unverified.
5. No history, no restatement, no essay past 8 lines.
6. Terminology matches the glossary, including in log lines and errors.
7. `ruff`, `mypy` (at the sub-project's current strictness) and the suite pass.

---

## 5.8 Open questions

### Q1 — How is a stop-and-ask actually delivered, at this scale?

Rule 3 says: if a reason matters and cannot be determined, **stop and ask**.
There are 683 comment lines. If even one in ten carries an unverifiable
rationale that matters, that is ~68 interruptions.

Stopping dead at each one makes the phase unworkable; not stopping breaks the
rule that matters most.

**Decided 2026-08-22: batch per file, escalate per sub-project.** While
rewriting, an unverifiable rationale is written into the file as unverified —
`# No derivation for this value is recorded in this repository.` — and added to a
list. At the end of each sub-project the list comes back as one set of questions.

**Two things this does not soften.** Anything that looks like a *defect* still
stops immediately, under the bug rule. And "record it and move on" is only
available for a rationale that is *missing*; a claim that can be checked must
still be checked before it is written.

### Q2 — Are test files held to the same standard?

**Decided 2026-08-22: yes, the same standard.** Docstrings, the comment budget
and **full type annotations**, with `tests/` inside the `mypy` ratchet like
everything else.

That is a larger phase than the first estimate. Measured after the decision:

| | src | tests | total |
| --- | --- | --- | --- |
| `mypy --disallow-untyped-defs` errors | 134 | **224** | **358** |
| — `global-identity-linker` | 22 | 22 | 44 |
| — `cas-to-postgres-importer` | 78 | 59 | 137 |
| — `webapp` | 34 | 143 | 177 |

The two runner scripts in the project-root `tests/` already pass strict `mypy`
with no errors.

> **This forces a change to how `mypy` is invoked.** Checking the three test
> suites together fails before it starts:
>
> ```text
> conftest.py: error: Duplicate module named "conftest"
> ```
>
> Three sub-projects each have a `tests/conftest.py`, and `mypy` cannot hold
> three modules of the same name in one run. `run-lint.sh` currently calls it
> once across all three `src/` roots; it must call it **once per sub-project**
> instead. That happens to be exactly what the ratchet wants anyway, since each
> sub-project reaches strict at a different time.

### Q3 — What is `schema_context.py`?

332 lines of prose inside a string constant, describing the database **to an
LLM**. It is not documentation for a human reader; it is a prompt. The comment
budget and the docstring rules do not obviously apply.

It is also the third description of the schema, alongside `schema.sql` and the
`docs/database.md` Phase 7 will write — flagged in Phase 3 §3.5 as needing an
owner, with a test suggested to catch drift.

**Decided 2026-08-22: document the module, leave the prompt text alone.** Phase 6
adds the drift test.

### Q4 — How far does the JavaScript type checking go?

Turning on `// @ts-check` across the 16 modules produces **40 `tsc` errors**,
mostly DOM narrowing — `Element` where `HTMLVideoElement` is meant. Each is fixed
by a JSDoc `@type` cast.

**Decided 2026-08-22: fix all 40 and add `tsc` to the lint service.**

Sequencing matters here: the 40 errors are fixed *first*, and `tsc` joins
`run-lint.sh` only once they are clean. Adding it before would put the lint gate
back into the permanently-red state that the E501 exemption exists to avoid.

### Q5 — Which project name wins? (D15)

| Surface | Says |
| --- | --- |
| `<title>` — browser tab | `DUUI Emotion Visualization` |
| `<h1 class="topbar-title">` | `Emotion Visualization` |
| `FastAPI(title=…)` — OpenAPI | `DUUI Video Emotion Visualization` |

**Decided 2026-08-22:** `DUUI Video Emotion Visualization` for the `<title>` and
the OpenAPI document; the `<h1>` stays `Emotion Visualization`. A page heading
does not need the framework prefix. Closes D15.

### Q6 — Does `cas/types.py` get a documentation pass?

224 lines of UIMA type names and injected fallback definitions, most of it inside
XML string literals whose `<description>` attributes are themselves prose. It is
exempt from the line limit already, as a data file that happens to end in `.py`.

**Decided 2026-08-22: module docstring and section comments yes; the XML strings
are data and are left alone.**

---

### Q7 — Does Phase 5 fix D4, or only document it?

`connect_timeout` is absent from every application module, so `create_app()`
hangs at startup against a host that blackholes packets rather than refusing.

It is on the ledger for this phase, but **it is a behaviour change, not a
documentation one** — and the value to choose is a judgement call: 2 seconds?
10? configurable? Under the bug rule that makes it a stop-and-ask.

**Decided 2026-08-22: fixed between Phase 5 and Phase 6, not inside either.**

Phase 5 documents the absence where it matters and changes no behaviour. The fix
then lands on its own, before the test audit begins — so the diff that changes
connection behaviour contains nothing else, and Phase 6 inherits a timeout it can
write a test against rather than one it has to add first.

### Q8 — Is the checkpoint a report, or a stop?

The plan stops after `global-identity-linker` to review the result against the
style guide and amend the guide if it did not survive contact.

That review can be mine — check the output against the guide, amend, report what
changed. Or it can be **yours**: five rewritten modules are a small enough sample
to read, and if the tone or depth is wrong, that is far cheaper to say after five
files than after a hundred.

**Decided 2026-08-22: a stop, and both of us review.** After
`global-identity-linker` the work halts. I check the five modules against the
style guide and report what I would change in the guide; you read them too.

The guide changed five times while being applied to *two* files in Phase 1. Five
modules is the last cheap sample before a hundred more.

## 5.9 Exit criteria

- [ ] Every code file documented to the guide, sub-project by sub-project
- [ ] 140 of 140 functions annotated; `mypy` strict on all three packages
- [ ] 16 of 16 JS modules under `// @ts-check`, `tsc` clean and in the lint service
- [ ] All seven ledger items (D4, D5, D7, D8, D10, D12, D15) resolved
- [ ] The `job_runs.py` pair diffed and its prose identical
- [ ] `viewer` gone from prose; glossary terminology throughout, including log lines
- [ ] **E501 exemption removed** from `run-lint.sh` and the hook; lint green
      with it enforced
- [ ] The unverified-rationale list delivered and answered
- [ ] Suite 150/150, all 13 checkers green, corpus row counts unchanged
