# Phase 1 — Style guide, documentation map, glossary

*Detailed plan for Phase 1. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[x]` complete, 2026-08-22.
Branch: `code-cleanup/phase-1`.

## 1.0 What this phase produces

Three artifacts, all decisions rather than prose. Everything Phases 2–9 write is
written against them, which is why nothing else may start until they are agreed.

| Deliverable | File | State |
| --- | --- | --- |
| Style guide | [`docs/documentation-style.md`](../documentation-style.md) | Done |
| Glossary | [`docs/glossary.md`](../glossary.md) | Done |
| Documentation map | [`docs/README.md`](../README.md) | Done |

## 1.1 Evidence the drafts are based on

Measured, not assumed:

| Question | Measurement |
| --- | --- |
| How wide is the code? | p50 = 40, p90 = 71, p95 = 75, p99 = 104. Only 91 lines exceed 88. |
| How wide is the prose? | Comments and docstrings already wrap near 72. |
| Which docstring opening dominates? | 217 open with a bare `"""` and the summary on the next line; 40 put the summary on the first line. |
| Do the four `job_runs` DDL copies agree? | **Yes — byte-identical** across `schema.sql` and all three Python modules. No drift. |
| Is the schema doc current? | ~~No~~ — **this reading was wrong; corrected in Phase 2.** `job_runs` is absent from `data_schema_with_types.md` because that file is the pipeline-export *design*, not a description of the database, and `job_runs` is operational. Its absence is correct. |
| What are the real `kind` / `modality` / `granularity` values? | Read from the live corpus, not from comments — see the glossary tables. |

The docstring measurement drives a real change: **the dominant style is the one
being replaced.** 217 docstrings currently put the summary on the line after
`"""`; the guide adopts the standard first-line summary. This is deliberate —
Phase 5 rewrites every docstring anyway, so the cost of standardizing is zero,
and tooling (`ruff`'s pydocstyle rules) can then check them.

## 1.2 Documentation map

**Moved to [`docs/README.md`](../README.md)** — it is a durable artifact that
Phase 7 builds against, and Phase 7 should not have to read a planning file to
find the structure it is implementing. That page is now the index for `docs/`
and carries the ownership table, the per-sub-project shape, and the five rules
that follow from it.

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

### Correction: existing comments carry no intent either

The first version of this section concluded that a comment recording *why* the
author chose something was evidence available nowhere else, and should be
preserved. **That was wrong, and the user corrected it:** nearly every comment in
this codebase was written by AI, not by the author. There is no authorial intent
in them to preserve. They are guesses that read like knowledge.

The rule is therefore simpler and stricter than the corollary it replaced:

- **Write only what can be verified** against code, schema, database, or tests.
- **An existing comment is never a source** — not for behavior, not for reasons.
- **If it matters and cannot be verified, stop and ask.** Never infer from
  plausibility; never let an existing comment settle the question.

Only the frontend style and accessibility material reflects real decisions, and
even that is kept because it is *verifiable* — `cvd_check.py` and
`contrast_check.py` check the palette claims — not because a comment asserts it.

**A third invented rationale surfaced while applying this.** My rewrite had kept
the original comment's claim that 0.30 suits "ArcFace-style 512-dimensional
embeddings", on the reasoning that the author's stated intent was worth
preserving. The `models` table records what actually produced the corpus's
embeddings: `w600k_r50` from InsightFace `buffalo_l`. That *is* an ArcFace-family
model, so the claim was approximately right — the most dangerous kind of wrong,
because it survives review. The verifiable fact was sitting in the database the
entire time. The comment now names the model and states that no derivation for
0.30 is recorded anywhere.

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

## 1.5 A sequencing problem the trial exposed

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

**Option 1 was approved and is done.** `docs/` now holds four stubs —
`architecture.md`, `configuration.md`, `database.md`, `operations.md` — each with
the headings the documentation map assigns it and HTML comments naming what
belongs in each section.

They are deliberately *structure without prose*. Writing the prose now would mean
writing it from the existing comments, which §2 of the style guide forbids. The
headings are what Phase 5 needs: a real page and a real anchor to link to when
rationale moves out of code.

**Plan consequence:** Phase 7 no longer invents the document set. It edits pages
that Phase 5 has already been appending to, and writes the connective prose. The
plan's decisions log records the move.

## 1.6 Work completed in this phase

- [x] Resolve Q1–Q4
- [x] Fold the answers into the style guide and glossary
- [x] Validate the guide against real code — see §1.4
- [x] Decide the `docs/` skeleton question in §1.5 — **approved, built**
- [x] Move the documentation map into a durable home — `docs/README.md`

## 1.7 Exit criteria

- [x] Style guide agreed — [`docs/documentation-style.md`](../documentation-style.md)
- [x] Glossary agreed, including Q1 and Q2 — [`docs/glossary.md`](../glossary.md)
- [x] Documentation map agreed and durably located — [`docs/README.md`](../README.md)
- [x] Guide validated against a real file, and amended from what that found
- [x] `docs/` skeleton built so Phase 5 has real link targets

**Phase 1 is complete.** Everything Phases 2–9 write is now written against
these three documents.

## 1.8 What this hands to later phases

| To | What |
| --- | --- |
| All | The style guide and glossary — binding, and the rule that existing comments are not evidence |
| Phase 2 | The doc map tells the ledger which document each verified fact belongs to |
| Phase 4 | Formatter and linter config must encode §8 of the guide: 88 columns for code, 72 for prose, US English |
| Phase 5 | Real `docs/` pages to move rationale into; the trial rewrite of `identity/config.py` and `db.py` as the worked example |
| Phase 7 | Edits pages Phase 5 has been appending to, rather than inventing the document set |
