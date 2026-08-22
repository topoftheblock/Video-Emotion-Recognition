# Phase 1 — Style guide, documentation map, glossary

*Detailed plan for Phase 1. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` drafts written 2026-08-22, awaiting review.
Branch: `code-cleanup/phase-1`.

## 1.0 What this phase produces

Three artifacts, all decisions rather than prose. Everything Phases 2–9 write is
written against them, which is why nothing else may start until they are agreed.

| Deliverable | File | State |
| --- | --- | --- |
| Style guide | [`docs/documentation-style.md`](../documentation-style.md) | Draft |
| Glossary | [`docs/glossary.md`](../glossary.md) | Draft |
| Documentation map | §1.2 below | Draft |

## 1.1 Evidence the drafts are based on

Measured, not assumed:

| Question | Measurement |
| --- | --- |
| How wide is the code? | p50 = 40, p90 = 71, p95 = 75, p99 = 104. Only 91 lines exceed 88. |
| How wide is the prose? | Comments and docstrings already wrap near 72. |
| Which docstring opening dominates? | 217 open with a bare `"""` and the summary on the next line; 40 put the summary on the first line. |
| Do the four `job_runs` DDL copies agree? | **Yes — byte-identical** across `schema.sql` and all three Python modules. No drift. |
| Is the schema doc current? | **No.** `job_runs` exists in `schema.sql` (line 293) but is absent from `data_schema_with_types.md`. |
| What are the real `kind` / `modality` / `granularity` values? | Read from the live corpus, not from comments — see the glossary tables. |

The docstring measurement drives a real change: **the dominant style is the one
being replaced.** 217 docstrings currently put the summary on the line after
`"""`; the guide adopts the standard first-line summary. This is deliberate —
Phase 5 rewrites every docstring anyway, so the cost of standardizing is zero,
and tooling (`ruff`'s pydocstyle rules) can then check them.

## 1.2 Documentation map — draft

Who owns what. The purpose is to make duplication impossible by construction:
every question has exactly one document that answers it, and the others link.

### Root

| Document | Audience | Owns | Must not contain |
| --- | --- | --- | --- |
| `README.md` | **A user, first.** Then anyone orienting. | What this is, the four parts and how they fit, prerequisites, one quickstart path, links onward. Two-minute read. | Configuration detail, architecture depth, operational procedure, anything a sub-project owns |
| `docs/documentation-style.md` | Contributors | How to write anything in this repo | Project facts |
| `docs/glossary.md` | Everyone | One name per concept | Explanations of how things work |
| `docs/architecture.md` | Developers | How the four parts fit; the shared contracts — database, video store, environment variables, `job_runs` | Per-part internals |
| `docs/configuration.md` | Users, operators | **Every** environment variable, in one place | Anything not a setting |
| `docs/database.md` | Developers | The schema, rewritten from `schema.sql`; replaces `pgvector-db/data_schema_with_types.md` | Application logic |
| `docs/operations.md` | Operators | Running, upgrading, backup, schema changes on an existing volume, CI | First-run instructions (README) |
| `docs/plan/` | This effort | The cleanup plan and its phases | Anything about the software itself |

### Per sub-project

Each of the four gets a `README.md` answering, in this order: **what it is, how
to run it on its own, how to configure it, how to test it, where the detail is.**
Self-contained enough to work on that part alone.

`<sub-project>/docs/` holds detail belonging to exactly one part —
`webapp/docs/accessibility.md` is the model, and the existing a11y set folds in
here.

### The duplication rules that follow

1. **Configuration lives in `docs/configuration.md`.** `.env.example` carries a
   one-line gloss per variable and links there. The README lists only the
   variables needed for a first run.
2. **The schema lives in `docs/database.md`**, generated from or verified
   against `schema.sql`.
3. **A sub-project README never explains a shared contract** — it links to
   `docs/architecture.md`. Otherwise the same explanation exists four times and
   drifts four ways.
4. **The root README never explains a sub-project.** It links.

## 1.3 Open questions for review

Four. The first two are the ones that matter.

### Q1 — "viewer" or "webapp"?

Both are in use: **92 occurrences of "viewer", 74 of "webapp"**, across code
comments, docstrings, the README, and Compose. They mean the same thing.

The directory is `webapp` and that name is fixed, so consistency argues for
**"the webapp"** everywhere and retiring "viewer". The counter-argument: "viewer"
describes what it does for a *user*, and the README is user-first.

**Recommendation: "the webapp."** One name, matching the directory the reader
will actually see. Keep "viewer" out of prose entirely rather than allowing it as
a soft alias, because a soft alias is how you end up with 92 of one and 74 of the
other.

### Q2 — what does `base_emotions` mean?

The table holds one emotion reading per (person, modality, granularity, span),
with VAD values and a dominant label; `emotion_scores` holds the per-label
distribution hanging off it. **Nothing in the code or comments explains what
"base" distinguishes.**

Three possibilities:

1. "Base" = the annotation the scores attach to. Then the docs should say so and
   the name stays.
2. It is a leftover with no current meaning. Then the concept is simply an
   *emotion annotation*, and the table is a Phase 3 rename candidate.
3. It means something specific from the upstream DUUI pipeline that is worth
   preserving.

**This needs your answer** — it is domain knowledge not recoverable from the
code. If it is (2), note that renaming a table is a schema migration touching
all three sub-projects and the live volume, so it may be worth documenting
rather than renaming.

### Q3 — em dash

The codebase uses `--` throughout. The guide specifies `—`. Files are UTF-8 and
already contain non-ASCII, so this is safe. Confirm, or keep `--` if you prefer
ASCII-only source.

### Q4 — is `docs/architecture.md` worth having?

The map proposes it to stop the four sub-project READMEs each re-explaining the
shared database and video-store contracts. It is one more file to maintain. The
alternative is letting the root README carry it, which fights the two-minute
target.

**Recommendation: keep it.** The contracts are exactly the thing that gets
explained four times and drifts.

## 1.4 Remaining work in this phase

- [ ] Resolve Q1–Q4
- [ ] Fold the answers into the style guide and glossary
- [ ] Confirm the documentation map, then move it from this file into a durable
      home (it is a Phase 7 input, and Phase 7 should not have to read a plan
      file to find it)
- [ ] Sanity-check the guide against one real file before Phase 5 depends on it
      — pick a small module, rewrite it fully to the guide, and see what the
      guide fails to answer

That last item matters more than it looks. A style guide that has never been
applied is a guess; Phase 5's checkpoint after the first sub-project exists for
the same reason, but catching the gaps on one file now is cheaper.

## 1.5 Exit criteria

- [ ] Style guide agreed
- [ ] Glossary agreed, including Q1 and Q2
- [ ] Documentation map agreed and durably located
- [ ] Guide validated against at least one real file
