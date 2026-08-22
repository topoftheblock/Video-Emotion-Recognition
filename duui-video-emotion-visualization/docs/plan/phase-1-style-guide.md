# Phase 1 — Style guide, documentation map, glossary

*Detailed plan for Phase 1. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[~]` drafts written and validated 2026-08-22. Q1–Q4 answered.
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

## 1.3 Review questions — answered 2026-08-22

| | Question | Answer |
| --- | --- | --- |
| Q1 | "viewer" or "webapp"? | **"webapp" everywhere.** "Viewer" is retired, not kept as an alias. |
| Q2 | What does `base_emotions` mean? | **The name is correct and stays.** Upstream models do not share an emotion inventory — the more granular ones are reduced to a common base set so video, text, and audio output are comparable. That reduction happens outside this project, during CAS creation, and is documented there. Say only that much here. |
| Q3 | Em dash | **Use `—`.** |
| Q4 | `docs/architecture.md` | **Yes, create it.** |

A note recorded while answering Q2: `dominant_label` and `emotion_scores.label`
are **model-native and differ by modality** in the current corpus — video uses
eight capitalized labels, text uses lowercase GoEmotions-style labels, audio its
own set, plus `<unk>` and empty values. The comparable axis across modalities is
valence/arousal/dominance, not the label. Written into the glossary so nobody
queries across modalities on `label` and assumes a shared vocabulary.

## 1.4 Validating the guide against real code

`global-identity-linker/src/identity/config.py` (53 lines) and `db.py` (10 lines)
were rewritten fully to the guide. Suite stayed green at 150/150.

The point was to find what the guide could not answer. It found five gaps, all
now closed in the guide:

### The one that matters: invented rationale

**Writing 60 lines while actively trying to follow the guide, I invented two
rationales that nothing in the repository supports.**

- For `DB_CONFIG`'s placeholder defaults I wrote that they exist so a
  misconfigured run "fails to connect rather than reaching an unintended
  database." Plausible, tidy, and entirely unverified — the placeholders may
  equally be an unfinished template. Phase 0 finding (c) is evidence *against*
  the charitable reading: they cause every DB-backed test to skip silently.
- For the voice threshold being looser than the face threshold I wrote "because
  voice embeddings separate speakers less sharply." True as general domain
  knowledge; not something this repository states.

Both now say what is actually known and name the uncertainty instead.

This is exactly the failure mode the whole pass exists to remove, reproduced
under controlled conditions in under an hour. It is not a discipline problem —
a plausible reason is easier to write than an admission of ignorance, and it
reads better. So the guide now carries it as **rule 2, above everything except
"the code is the source of truth"**, with an explicit escape hatch: write the
uncertainty down.

A corollary was needed, because rules 1 and 2 conflict on one point: a comment
claiming **what the code does** must be verified and rewritten if wrong, while a
comment recording **why the author chose something** is evidence available
nowhere else and should be preserved, marked as intent where unconfirmed. What
is forbidden is *supplying* an intent the author never recorded.

### The other four

1. **Do docstrings fall under the 8-line rule?** The original module docstring
   was 16 lines, most of it arguing why the three configs are separate. Resolved:
   docstrings are exempt from the *count*, not the *principle* — length is fine
   for describing what a module owns, not for arguing a design decision. The
   test is what the text is doing, not how long it is.
2. **Where does moved rationale go when the target page does not exist?** I
   wrote "see docs/architecture.md" — a forward reference to a Phase 7 file. See
   §1.6; this one has a plan consequence.
3. **One comment per constant, or one block per group?** Resolved: one each. A
   shared block leaves the second constant undocumented for anyone who lands on
   it directly.
4. **Are module constants annotated?** Resolved: only where inference is wrong
   or unclear. `MIN_WRITE_INTERVAL = 1.0` needs nothing; `DB_CONFIG` earns it.

## 1.4 Remaining work in this phase

- [x] Resolve Q1–Q4
- [x] Fold the answers into the style guide and glossary
- [x] Validate the guide against real code — see §1.4
- [ ] Decide the `docs/` skeleton question in §1.6
- [ ] Move the documentation map into a durable home (Phase 7 should not have to
      read a plan file to find it)

## 1.6 A sequencing problem the trial exposed

**Phase 5 writes in-file documentation. Phase 7 creates `docs/`. That is the
wrong way round**, and the trial run hit it immediately.

The comment budget sends every over-long rationale to a `docs/` page. Rewriting
*one* 53-line file produced a forward reference to `docs/architecture.md`, which
does not exist yet. Phase 5 covers roughly fifty files and will produce these
constantly. Three ways out:

1. **Create the `docs/` skeleton early** — stub pages with real headings, from
   the documentation map, at the end of this phase or during Phase 2. Phase 5
   appends rationale to a real page as it goes; Phase 7 then organizes and
   writes connective prose instead of inventing structure from scratch.
2. Park moved rationale in a staging file for Phase 7 to distribute. Keeps the
   phases clean, but every link is broken until Phase 7 lands, and the staging
   file becomes exactly the kind of dumping ground this pass is removing.
3. Move Phase 7 before Phase 5. Rejected — it contradicts the ordering principle
   in §3 of the plan, since READMEs must describe a finished state.

**Recommendation: option 1.** It costs an hour now, keeps every link valid the
moment it is written, and turns Phase 7 from an authoring job into an editing
job. Needs your agreement, since it moves work between phases.

## 1.5 Exit criteria

- [ ] Style guide agreed
- [ ] Glossary agreed, including Q1 and Q2
- [ ] Documentation map agreed and durably located
- [ ] Guide validated against at least one real file
