# Phase 5 — In-file documentation rewrite

*Detailed plan for Phase 5. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` plan drafted 2026-08-22. Q1, Q3–Q6 answered; Q2 and two new
questions open — §5.8.
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
| Functions with a return annotation | **7 of 140** | 140 |
| `mypy --disallow-untyped-defs` errors | **134** (22 + 78 + 34) | 0 |
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
leaving everything lenient and flipping one switch at the end:

```toml
[[tool.mypy.overrides]]
module = ["identity.*"]
disallow_untyped_defs = true
```

A finished sub-project is then held to the strict setting and **cannot regress
while the next one is in progress**. By the end, strict is already on everywhere
and there is no cliff. The per-sub-project error counts above are the size of
each step: 22, then 78, then 34.

### The checkpoint

**After `global-identity-linker` — the first sub-project with code — stop.**
Review the result against the style guide, amend the guide if it did not survive
contact, *then* continue. The guide has been applied to exactly two files so far
(`identity/config.py` and `identity/db.py`, in Phase 1) and it changed five times
during that exercise.

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

23 test modules. Their docstrings are genuinely valuable — a test's docstring
should say *why this test exists*, which is the one thing the assertions cannot.

But full annotation is a different matter: `def test_x() -> None:` on 150 tests
adds 150 annotations that say nothing. **Proposal: docstrings and comment budget
yes, `disallow_untyped_defs` no** — exclude `tests/` from the mypy ratchet.

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

**Proposal: document the absence where it matters, and leave the fix out of this
phase.** Phase 6 is where a timeout could actually be tested; changing connection
behaviour in the middle of a prose rewrite puts two kinds of risk in one diff.

### Q8 — Is the checkpoint a report, or a stop?

The plan stops after `global-identity-linker` to review the result against the
style guide and amend the guide if it did not survive contact.

That review can be mine — check the output against the guide, amend, report what
changed. Or it can be **yours**: five rewritten modules are a small enough sample
to read, and if the tone or depth is wrong, that is far cheaper to say after five
files than after a hundred.

**Proposal: yours.** The guide changed five times while being applied to *two*
files in Phase 1. This is the last cheap moment to find out it is still wrong.

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
