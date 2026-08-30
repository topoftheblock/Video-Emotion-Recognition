# Phase 8 — Final sweep

Branch: `code-cleanup/phase-8`. The last substantive phase: Phase 9 is
lockfiles and changelogs and nothing else.

Every earlier phase checked its own work against its own rules. This one
checks the *result* — the whole doc set read in sequence, the whole
project verified from nothing, and the two enforcement gaps that let
Phase 7's findings sit undetected in the first place.

---

## 8.1 What is binding

[§5 of the plan overview](README.md), the
[style guide](../documentation-style.md) and the
[glossary](../glossary.md) apply unchanged, as always. Two rules from
Phase 7 carry forward and are worth restating, because this phase is
where they get tested at scale:

- **Every command is run, not read.**
- **`docs/legacy/` is not a source.** It no longer exists. Nothing may
  be recovered from git history to fill a gap found here; a gap is
  filled from the code, the schema or the database, or it is recorded.

### One rule this phase adds

**A rename and a rewrite never share a commit.** §5 already says this.
It matters here because the largest item (§8.3) is a rename touching 29
files, and the temptation to fix the prose around each one while passing
through is exactly how a reviewable diff stops being reviewable.

## 8.2 The starting state, measured 2026-08-30

### The doc set is 17 documents and 2,605 lines

| | Lines |
| --- | --- |
| Root `README.md` | 87 |
| `docs/` — map, architecture, configuration, database, operations | 768 |
| `docs/` — glossary, style guide, todo | 717 |
| Four sub-project READMEs + `tests/README.md` | 487 |
| `webapp/docs/` — accessibility set | 546 |

Nobody has read them in sequence. Phase 7 checked each page against its
own row in the map, which finds a page that says the wrong thing and
cannot find two pages that disagree.

### Cross-document facts, checked now and consistent

Spot-checked before writing this, so the reading pass starts from a
known state rather than suspicion:

- **Postgres 18** — stated in `pgvector-db/README.md`, `glossary.md` and
  `docker-compose.yml`. Consistent.
- **Fourteen tables** — only `database.md` says it. No drift surface.
- **28 settings, 22 passed through, 6 not** — only
  `configuration.md` counts them. `.env.example` lists them without a
  total.

### One gap the spot-check found

**No shipped document names the Python version.** Three sub-project
READMEs say "with the project's Python and the requirements installed",
which a reader cannot act on. `3.14` appears in the four Dockerfiles and
in three commands inside `webapp/docs/accessibility.md`, and nowhere a
reader would look for a prerequisite.

## 8.3 British spellings — 29 files, 185 occurrences

Found in Phase 7 and deliberately left, because it is a rename.

§8 of the style guide says US English everywhere, including code
comments and log output. Nothing enforces it: `ruff` and `mypy` do not
spell-check and `stylecheck.py` has no rule for it.

### What is actually affected

Measured, not estimated:

| Where | Files | Occurrences | Kind |
| --- | --- | --- | --- |
| Shipped files | 29 | 185 | see below |
| `docs/plan/` | 6 | 30 | historical record |

**The frontend half is comment-only and carries no risk.** Every hit in
`webapp/src/frontend/` — `state.js`, `player.js`, `adaptive.css`,
`tokens.css` and the rest — is inside a comment. No selector, no custom
property, no identifier, and **no user-facing string anywhere in the
project** matches. Checked by searching string literals separately.

**Ten identifiers do have to be renamed**, all in `webapp/tests/`:

    load_person_colours                     (defined in support/contrast_check.py,
                                             called from test_contrast.py — the one
                                             that crosses a file boundary)
    test_forced_colours_covers_everything_whose_background_is_data
    test_non_colour_declarations_are_skipped
    test_no_two_person_colours_converge_under_any_deficiency
    test_readable_text_color_clears_aa_for_every_person_colour
    test_simulation_is_a_no_op_for_a_neutral_colour
    test_suppressed_outlines_have_a_forced_colours_fallback
    test_the_colour_scheme_is_declared
    test_the_on_video_label_colour_comes_from_the_shared_decision
    test_unknown_person_grey_separates_from_every_assignable_colour

**One hit is neither prose nor a test name.**
`webapp/src/backend/queries/stats.py:44` uses `labelled` as a SQL
subquery alias. Renaming it is a code change, small and contained, but
it belongs in the rename commit and not in a prose pass.

### Two things that must not be "corrected", and one that must

- **Ubuntu Font Licence** — the license's actual name.
- **`forced-colors`** — the CSS media feature, already US-spelled in
  every rule. Only the prose *around* it says `forced-colours`.
- ~~`grey`~~ — **not an exception; see the decision below.** Thirteen
  occurrences: the Okabe-Ito palette's neutral is discussed as "the
  unknown-person grey" in `state.js`, `cvd_check.py`, `accessibility.md`
  and two stylesheets. Renaming the *concept* means
  renaming it in the accessibility record too, which is a frozen
  before-picture. **Decide once, apply everywhere or nowhere** — and if
  the answer is "everywhere", `test_unknown_person_grey_...` moves with
  it.

### Whether `docs/plan/` is included

**Decided: no.** The 30 occurrences there are in phase records that
document what was found and decided on a given date. They are evidence,
not documentation, and rewriting them edits the record. The style guide
binds what the project *says*; the plan is how it got there. The
checker added in step 8 has to exempt `docs/plan/` for the same reason.

## 8.4 The checker gap is wider than `.sql`

Phase 7 extended `stylecheck.py` from three sub-projects to the whole
project, which was the large half. The rest is file *types* it still
does not recognize.

`CHECKED_SUFFIXES` is `.py .toml .js .css .html .sh .yml`, plus
`Dockerfile*`, `.dockerignore` and `requirements.txt` by name. That
leaves tracked files carrying real prose unread:

| File | Comment lines | Why it is missed |
| --- | --- | --- |
| `.env.example` | 92 | no suffix rule matches |
| `tests/hooks/pre-commit` | 32 | a shell script with no `.sh` |
| `eslint.config.cjs` | 13 | `.cjs` |
| `.markdownlint-cli2.jsonc` | 12 | `.jsonc` |
| `.sqlfluff` | 12 | no suffix |
| `.yamllint` | 10 | no suffix |
| `.prettierignore` | 6 | no suffix |
| `pgvector-db/schema.sql` | 60 | `.sql` |

`.env.example` is the sharp one: 92 comment lines, rewritten from
scratch in Phase 7, and the file a user is most likely to read. Its
widths were checked by hand, which is precisely the arrangement this
checker exists to replace.

### `schema.sql` is the interesting case, and it is not free

Measured: **60 comment lines, 20 of them over 72 columns, and one
legacy `--` em dash inside a comment.** So the file has real findings
waiting.

The subtlety: in SQL, `--` is both the comment marker *and* the thing
the em-dash rule looks for. `prose_lines()` needs a `.sql` branch
matching `^\s*--`, and the em-dash rule then has to skip the marker it
just used to identify the line. Get that wrong and every comment line
in the file reports a false em dash.

**Write the test first.** A fixture with a correct SQL comment, one over
width, and one containing a real legacy `--` between words, asserting
one finding each and none for the markers.

## 8.5 Verification from nothing

Phase 7's rehearsal started from a clean *volume*, in a working tree
that already had everything. This starts from a clean *checkout*, which
is what catches anything the documents assume you already have —
including the Python version gap in §8.2.

    git clone <this repo> /tmp/fresh && cd /tmp/fresh/duui-video-emotion-visualization

Then follow the root README and nothing else, in order, doing only what
it says. Every place the clone needs something the page did not mention
is a finding.

Two things to watch for specifically:

- **`.env`.** The README says to copy `.env.example`. A fresh clone has
  no `.env`, and the stack is supposed to run without one. Confirm that
  is true rather than assuming it.
- **Host ports.** The rehearsal must not collide with the running stack.
  Use a separate Compose project and different ports, as Phase 7 did.

## 8.6 CI — blocked on a push, and it has to be said

The plan schedules "confirm the lint workflow fires on a change inside
this project and stays silent on one outside it" for this phase. **It
cannot be done from here.**

- `gh` is not installed and neither is `act`.
- The workflow has never run: nothing in this cleanup has been pushed.
  `origin/code-cleanup/main` is 15 commits behind the local branch.

What *can* be done locally, and should be:

1. `actionlint` on both workflows — already in the lint pass for
   `a11y-ci.yml`, and by hand for the real one, which lives outside the
   mount.
2. Read the `paths:` filters against the actual repository layout and
   confirm by inspection that a sibling project's path cannot match.
3. Run the two commands the workflow runs — `docker compose run --rm
   lint` and `... tests` — which is the whole of what it does.

**The observation itself needs the owner to push.** Then: one commit
touching a file inside this directory should trigger it, one touching a
sibling should not. Until that happens the item stays open, and the
phase does not claim it. Recording an unverified claim as verified is
the failure this whole plan exists to correct.

### What was checked locally, 2026-08-30

1. **`actionlint` on both workflows** — the project's and the sibling
   `ci.yml`. Both clean.
2. **The `paths:` filters, against the actual repository.** The workflow
   filters on `duui-video-emotion-visualization/**` and on its own path.
   Matched against every tracked file in the repository: **201 files
   inside this project, all matched; 179 outside it, none matched**,
   across 11 sibling top-level directories. So the scoping is right as
   written — what remains unverified is that GitHub behaves the way the
   filter says, not the filter itself.
3. **The two commands the workflow runs**, which are the whole of what
   it does: `docker compose run --rm lint` and `... tests`. Both green,
   and now green from a fresh clone as well, which they were not before
   §8.5.

### Still open

**Nobody has seen this workflow run.** By the project owner's decision
the phase waits for that rather than closing around it.

**And pushing the cleanup branch will not produce a run.** Checked while
merging: the workflow's `push` trigger is scoped `branches: [main]`, so
only a push to `main` fires it. A push of `code-cleanup/main` matches the
`paths:` filter and still does nothing, because the branch filter is
evaluated first. Three ways to actually see it:

1. **Open a pull request** from `code-cleanup/main` to `main`. The
   `pull_request:` trigger carries the same `paths:` filter and no branch
   filter, so this fires. It is also how the final merge should happen,
   so the run is not make-work.
2. **`workflow_dispatch`** — the manual button, already declared. Fires
   on demand but proves nothing about the filters, since a manual run
   ignores them.
3. **Wait for the final merge to `main`**, which is the end of Phase 9.

Option 1 is the one that observes what the plan actually wants. The
second half — that a sibling project's change stays silent — needs a
commit touching only a sibling, which is nothing this cleanup should
manufacture; it is best observed opportunistically the next time one
changes.

## 8.7 Small things found while measuring

- **`cas-to-postgres-importer/cas/`** is an empty untracked directory,
  created by a native run defaulting `DUUI_INPUT_XMI_DIR` to `cas`. It
  sits confusingly beside `src/importer/cas/`, which is a package.
  Either gitignore it or change nothing — but decide rather than leave
  it.
- **The licensing decision in [§7 of the plan](README.md) says
  `python:3.12-slim`.** Phase 4 moved to 3.14. The decision itself is
  unaffected — it is about redistribution, which still is not happening
  — but the fact is stale.

## 8.8 Steps

One commit each, in this order. The rename is deliberately last of the
edits, so that nothing else is in flight while a 29-file mechanical
change lands.

| # | Step |
| --- | --- |
| 1 | Answer §8.9 |
| 2 | Read all 17 documents in sequence; record findings before fixing any of them — done, §8.11 |
| 3 | Fix what the reading found — contradictions, gaps, terminology drift — done |
| 4 | Name the Python version where a reader needs it (§8.2) — done |
| 5 | Teach `stylecheck.py` the eight unread file kinds, test-first for `.sql` (§8.4) — done |
| 6 | Fix what that finds — 72 findings in all — done |
| 7 | The British-spelling rename, prose and identifiers, in its own commit (§8.3) — done, 38 files |
| 8 | Add the spelling rule to `stylecheck.py`, in a second commit, so it cannot come back — done |
| 9 | Fresh-clone verification (§8.5) — done, and it found two real defects |
| 10 | The CI checks that can be done locally (§8.6); record the rest as open — done |
| 11 | Settle §8.7 — done |
| 12 | Close — **waiting on the push**, per §8.9 answer 3 |

## 8.9 Questions, answered

Answered 2026-08-30.

1. **The rename excludes `docs/plan/`.** Those are dated records of what
   was found and decided; rewriting them edits the evidence. The 30
   occurrences there stay, and the checker must not fail on them.
2. **"grey" becomes "gray"**, everywhere it appears — prose, the palette
   concept, the identifier, and the accessibility record with it. One
   spelling, applied across all five files.
3. **The phase waits for a push** rather than closing with CI
   unobserved. Everything else is finished first; the phase stays open
   on that one item until the workflow has actually run.
4. **`cas-to-postgres-importer/cas/` is deleted** if it is genuinely
   redundant — verify what creates it and whether anything needs it
   before removing it, rather than assuming.

## 8.10 Exit

- Every checker green, including `stylecheck.py` over the eight file
  kinds it could not read before.
- Full suite green; all four images build.
- The 17 documents read end to end, with what that found either fixed or
  recorded in `docs/todo.md`.
- No British spelling left in a shipped file, and a rule that fails the
  build if one returns — **in the documents as well as the code**. The
  first version of that rule reached neither: `stylecheck.py` did not
  read `.md` at all, so the 17 documents, which held most of the 185
  occurrences, were clean only because they had been corrected by hand.
  Markdown now gets the spelling rule and nothing else: its width
  belongs to markdownlint at 80, its `--` cannot be told from a
  documented flag inside a fence, and the one document most full of
  retired terms is the glossary, which has to name them to retire them.
  `docs/plan/` is exempt, per §8.9 answer 1.
- A fresh clone reaches a working stack following only the root README.
- CI either observed, or recorded as unobserved with the reason.

---

## 8.11 What reading all 17 in sequence found

Recorded before anything was fixed, so the list is what the reading
produced rather than what survived the fixing.

**The pattern is the same twice: a phase corrected a claim at one site
and did not look for the same claim elsewhere.** Neither is findable by
checking a page against its own row in the map, which is what Phase 7
did. Both need two pages open at once.

### F1 — Two documents disagree about whether the repository has CI

`webapp/docs/accessibility.md`, under "Not implemented":

> **There is no CI.** […] It was left inert deliberately: the repository
> root is a monorepo of a dozen unrelated subprojects, and switching on
> GitHub Actions there affects all of them.

`webapp/docs/a11y-ci.yml`, rewritten in Phase 7, ten lines of argument
saying the opposite: the repository has two workflows, a `paths:` filter
keeps one off the siblings, and the file is inert because it is
**redundant** — the project workflow already runs those five suites.

Phase 7 fixed the header and never asked who else said it. The
accessibility page is the wrong one, and it is the one a person reads
first.

### F2 — And about why the browser checks are not automated

`accessibility.md`: "Driving it headlessly means adding a JavaScript
toolchain and a browser download to a repository that is Python end to
end."

`webapp/tests/a11y_browser_check.js`, corrected in Phase 6: "The project
does now carry a JavaScript toolchain, but running this would
additionally mean downloading a browser."

Phase 4 added the toolchain — eslint, prettier, stylelint, `tsc` and
Node in the lint image. Phase 6 corrected the justification in the
script and not in the page. The decision is unchanged and correct; only
half of its stated reason is still true.

### F3 — A dated record read as a current one

`a11y-verification.md` prints three checker results under "Static
checkers". Two are still exactly right today — `contrast_check.py` gives
79 pairs, 0 failing, 15 unasserted; `cvd_check.py` gives 0 below dE2000
10.0. The third, `pytest 11 passed`, matches nothing now: those five
files give **43**, and `test_contrast.py` alone gives 7.

The file is a record of a run on 2026-08-20 and says so. The block does
not, so a reader checks it and finds it wrong. **Do not update the
number** — that falsifies the record. Label the block with what it is.

### F4 — "The only supported way" is contradicted two documents later

The root README: "This is the only supported way to run the suite."
`accessibility.md` then gives a `docker run … python:3.14-slim … pytest`
command for five test files.

Both are right about different things — one is the suite, the other a
subset that deliberately needs no database and no dependencies — but the
word "only" makes them read as a contradiction. Narrow the claim.

### F5 — Two more British spellings the Phase 7 measurement missed

`judgement` and `defence`, both in `accessibility.md`. The §8.3 scan
searched a fixed word list that did not include them, which is an
argument for the checker rule in step 8 being pattern-based rather than
another fixed list.

### Not a finding, checked and sound

- **Postgres 18** agrees across `pgvector-db/README.md`, `glossary.md`
  and `docker-compose.yml`.
- **The standing-decisions tables** in `accessibility.md` and
  `a11y-verification.md` overlap by nine rows and do not disagree.
- **No shipped document uses "viewer"**, "global identity" or any other
  retired term. Phase 7's glossary pass holds.
- **Every path named in prose still resolves**, re-run over the larger
  set.

---

## 8.12 What the fresh clone found

Neither defect was visible from the working tree, which is the whole
argument for the step.

### F6 — `.coverage` was committed

A 53 KB binary coverage database, written by a `--cov` run and committed
by accident during Phase 6. Tracked, in `.gitignore` nowhere, and in
every clone since. Untracked and ignored, with `htmlcov/`.

### F7 — the test and lint services did not work from a clone

The serious one.

    $ docker compose run --rm tests
    /bin/sh: 0: cannot open /app/tests/run-tests.sh: Permission denied

On a labelling distro a fresh checkout is `user_home_t` or `user_tmp_t`,
which `container_t` may not read. Both services mount the project at
`/app` and neither mount carried the `z` flag, so both died on their own
entry point with a message that names no cause.

**The compose file already knew.** The importer's input mounts carry `z`
and a paragraph explaining precisely this failure, written in an earlier
phase. The tests and lint mounts were never given the same treatment,
and nothing caught it because every check in every phase ran from a
working tree whose label had already been changed to
`container_file_t` by those very mounts.

So the two commands the README pushes hardest failed for anyone
following it, on the distribution family this project is developed on,
and eight phases of verification could not see it.

Fixed by adding `z` to both. Verified by cloning to `/tmp`, confirming
the label was `user_tmp_t`, and running both services from there: 215
tests pass and every checker is green, where before neither started.
