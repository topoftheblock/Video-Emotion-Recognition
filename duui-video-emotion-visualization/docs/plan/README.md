# Cleanup & Documentation Plan

Living document, and the **single home** for anything cross-cutting: the phase
order, the constraints, the rules, the decisions already made (§7), and the
progress log (§8).

Per-phase detail lives in its own `phase-N-*.md` beside this file, written when
that phase starts — see the index in [§9](#9-detailed-phase-plans).

---

## 1. Scope and fixed constraints

### Must not change

- The names of the four sub-projects: `webapp`, `cas-to-postgres-importer`,
  `global-identity-linker`, `pgvector-db`.
- The inner layout of a sub-project: `src/`, `tests/`, `.dockerignore`,
  `Dockerfile`, `pyproject.toml`, `requirements.txt`.
  **Exception:** `pgvector-db` is a database image, not an application. It needs
  no `src/` or `tests/` and is not to be forced into the shape (decided
  2026-08-22).
- **Sub-projects never share files.** Each must stay standalone and
  self-contained; no shared/common package, no cross-project imports, no
  symlinks. Duplication between sub-projects is accepted as the price of that
  independence (decided 2026-08-22) — see the documentation rule in §5.

Everything *inside* `src/` and `tests/` (package names, module names, how code
is split across files) is in scope — the constraint is the shape of the
sub-project, not its contents.

### Goals

1. A README per sub-project; root README reduced to the minimum that still
   covers the project as a whole. `docs/` folders carry the detail.
2. One documentation style, applied everywhere.
3. Real in-file documentation for every code file and every function.
4. A full rewrite of AI-written comments/docs: delete what is not needed,
   correct what is wrong, add what is missing.
5. Reviewed: dependency and Python versions; file/module split and naming;
   package and folder naming; test redundancy and test gaps.

---

## 2. Starting state (audited 2026-08-22)

Grounding facts the plan is built on. Re-verify before acting on any of them.

| Area | Finding |
| --- | --- |
| Root `README.md` | 968 lines / ~6,400 words / 43 KB. Carries almost all project documentation. |
| Sub-project READMEs | None exist. Only `webapp/docs/` exists (accessibility docs, 4 files). |
| Stale project name | `bundestag` appears in **18 files**, incl. `docker-compose.yml` (`name: duui-bundestag-stack`), the README title, and many code comments — leftovers from commit `09dc495`. |
| Broken doc reference | `webapp/docs/a11y-ci.yml` instructs `git mv duui-bundestag-stack/webapp/…` — that path no longer exists. |
| Package names | `main` (importer), `backend` (webapp), `identity` (linker). `main` is a non-name; root `pyproject.toml` explains they must stay *mutually distinct* because all three `src/` roots share one `pythonpath`. |
| Duplication | `job_runs.py` is ~257 lines in both jobs and differs by 35 diff lines, nearly all comment text. Three separate `config.py` and `db.py` too (10–341 lines). Deliberate, per the no-shared-files rule — but the two copies' comments have drifted apart. |
| Type hints | 6 of 140 function definitions have a return annotation. Parameter annotations are near-absent. |
| Comment style | Long narrative rationale essays; `--` for em-dashes; `# --- Banner ---` section rules; JSDoc-shaped `/** */` blocks without `@param`/`@returns`. Density varies wildly (`config.py` 146 comment lines / 341; `schema_context.py` 13 / 355). |
| Accessibility checks | `contrast_check.py`, `cvd_check.py`, `markup_check.py` are **support libraries already imported by real pytest modules** (`test_contrast.py`, `test_palette.py`, `test_markup.py`, `test_stylesheets.py`) — they are simply not named `test_*`. Only `a11y_browser_check.js` is genuinely manual: it needs a live browser and pulls axe-core from a CDN. |
| `pgvector-db` | No `src/`, `tests/`, `pyproject.toml`, `requirements.txt`, `.dockerignore`. Holds `schema.sql` and `data_schema_with_types.md`. Confirmed correct — it is a database image, not an application. |
| Versions | `python:3.12-slim` ×3; `pgvector/pgvector:pg16`. All deps floor-pinned (`>=`), no upper bounds, **no lockfile**. |
| Tooling | No linter, no formatter, no `CLAUDE.md`, no `LICENSE`, no `CONTRIBUTING`. |
| CI | **The repository does have CI** — `.github/workflows/ci.yml` at the git root — but it targets the *predecessor* project `duui_bundestag_pipeline/` (`working-directory:` set to it, referencing its `importer/`, `db/schema.sql`, `build-all.sh`). It is valid and working; it simply does not cover this project, which has none. |
| Doc error, consequential | `webapp/docs/a11y-ci.yml`'s header states "This repository has no CI at all" as the reason it was left inert. **That is false** and was probably false when written. See the note under §7 item 3. |
| Live data | The stack is running with **real imported data**: 10 videos, 375,205 emotion scores, 42,930 face detections, in volume `duui-bundestag-stack_db_data`. |
| ⚠️ Rename hazard | Compose derives volume names from the project name (`name: duui-bundestag-stack`, line 38). Changing it orphans the database and the video store. Data is reproducible, so this costs time rather than work — but it must be deliberate. See Phase 3 and [phase-0-baseline.md](phase-0-baseline.md) §0.2(a). |
| Sibling projects | The git root holds ~13 unrelated directories, including `duui_bundestag_pipeline/` — a tracked, older generation of this same project (`importer/`, `db/`, `webapp/`, `shared/`). Out of scope, but relevant to the name purge: it is a *sibling*, not ours, and must not be renamed. |
| `.env.example` | 4.7 KB, pure prose comments, no uncommented values. Overlaps the README's "Configuration reference" section — two sources of truth. |

---

## 3. Ordering principle

Four rules drive the order below.

1. **Decide the style before writing to it.** Every later phase produces prose;
   all of it must obey one guide, or the pass has to be redone.
2. **Establish what is true before writing it down.** The existing docs are
   partly wrong. Rewriting from them launders errors into the new docs.
   A verified fact ledger comes before prose.
3. **Move and rename before documenting.** A file documented and then renamed
   is documented twice. All structural churn lands before the doc rewrite.
4. **Prose describing the final state is written against the final state.**
   READMEs are the last writing task, not the first.

The costly failure mode is writing polished documentation for a structure that
then changes. Phases 1–4 exist to make that impossible.

---

## 4. Phases

Status: `[ ]` not started · `[~]` in progress · `[x]` done

---

### `[x]` Phase 0 — Baseline and safety net

**Why first:** every later phase is a large-scale edit. Without a green
baseline there is no way to tell a refactor regression from a pre-existing
failure.

- Get all three test suites running and record the result (including which
  need Postgres and which skip without it). Document how to reach green.
- Stand up the stack once end-to-end (`docker compose`), confirm the documented
  quickstart actually works. Note every step that does not.
- Record the baseline in this file — it is the reference for "did we break it".
- Decide the working method: branch per phase, one commit per logical step,
  suites green before each commit.

**Exit:** a known-good, reproducible baseline written down here.

---

### `[x]` Phase 1 — Documentation style guide + documentation map

**Why here:** the contract every later phase writes against. Two deliverables,
both decisions rather than prose.

**1a. Style guide** → `docs/documentation-style.md`

Must settle, concretely, with a good and a bad example for each:

- **Docstring format** for Python: which convention (Google / NumPy / plain
  prose), what a module docstring covers vs. a function docstring, whether
  `Args:`/`Returns:`/`Raises:` are mandatory.
- **Type hints: adopted** (decided 2026-08-22). Every function gets annotated
  parameters and a return type. The consequence for this guide is the important
  part: **docstrings no longer describe types.** The signature owns that; the
  docstring covers purpose, meaning, units, and edge cases. Write the rule that
  way, with an example, or the two will duplicate each other and drift.
- **Comment budget**: when an inline comment is warranted (non-obvious *why*)
  and when it is noise (restating the *what*). This is the rule that cuts the
  current prose down; it needs to be sharp enough to apply mechanically.
- **Where rationale lives**: long "why we chose this" passages belong in
  `docs/`, not in a 40-line block comment above a 3-line function. Define the
  length threshold at which a comment becomes a doc page with a link.
- **JS**: JSDoc with `@param`/`@returns`, or prose blocks. Pick one.
- **CSS / SQL / Dockerfile / compose / `.env.example`**: header block format and
  section-comment format for each.
- **Mechanics**: em-dash style (currently `--`), line width, heading case, and
  a terminology glossary (one canonical term each for video / CAS / person /
  global person / job / run). **Language: US English** (decided 2026-08-22) —
  set a spell-check target for it. Formatter config (Phase 4) must encode
  whatever is mechanically enforceable here.

**1b. Documentation map** → recorded in this file

Decide *which documents exist and what each one owns*, before any are written.
This is what keeps the root README, the four sub-READMEs and the `docs/` pages
from re-duplicating the current 968-line README in five places. For each
planned document: its audience, the questions it answers, and — explicitly —
what it must **not** cover because another document owns it.

**Exit:** style guide written; doc map agreed and recorded below.

---

### `[x]` Phase 2 — Fact ledger (what the system actually does)

**Why here:** supplies the source material for every rewrite in phases 5 and 7,
and is the only defence against copying existing errors forward.

- Read each sub-project and write down, per module, what it *actually* does —
  verified against the code, not against its current comments.
- Log every discrepancy found between existing docs/comments and reality. Known
  starting set, all already confirmed:
  - the stale `bundestag` naming across 18 files;
  - `webapp/docs/a11y-ci.yml`'s dead `duui-bundestag-stack/…` path;
  - **`webapp/docs/a11y-ci.yml`'s claim that the repository "has no CI at all"**,
    which is false — `.github/workflows/ci.yml` exists at the git root. Fixed in
    Phase 7; recorded here so the reasoning it supports is not copied forward
    anywhere else;
  - `pgvector-db/data_schema_with_types.md` vs. `schema.sql`;
  - README claims about commands and paths, none yet verified.

  Collect and log here; the fixes land in Phase 7. (Bugs in *code*, as opposed to
  errors in docs, follow the stop-and-ask rule in §5 instead.)
- Map the real contracts between sub-projects: the database schema, the video
  store path, the env vars, the job-status table. These are what the sub-project
  READMEs will each need to state consistently.
- Verify `pgvector-db/data_schema_with_types.md` against `schema.sql` and record
  the drift.

**Exit:** a per-sub-project fact ledger under `docs/`, plus a discrepancy list
feeding phases 3, 5 and 7.

---

### `[x]` Phase 3 — Structure: naming, splitting, merging

**Why here:** all path-changing churn in one place, before anything is written
about those paths. Split into *decide* then *execute* — the decisions are
reviewable, the execution is mechanical.

**3a. Decision document** → `docs/structure-decisions.md`

Named questions to answer, each with a rationale:

- **Package names.** `src/main/` → keep `main`, or rename to `importer`? Both
  acceptable (decided 2026-08-22), so this is a judgement call, not a blocker.
  Renaming touches `Dockerfile` `ENTRYPOINT`, `pyproject.toml`, every import and
  the tests; the one hard constraint from root `pyproject.toml` is that the
  three package names stay mutually distinct.
- ~~**The `job_runs.py` duplication.**~~ **Resolved:** the duplication stays.
  Sub-projects do not share files (§1). What remains is a Phase 5 task, not a
  Phase 3 one: bring the two copies' *documentation* into alignment so the same
  code does not carry two divergent explanations.
- **Oversized modules.** `config.py` (341), `pipeline.py` (373), `media.py` (363),
  `linking.py` (333), `schema_context.py` (355), `emotions.js` (359),
  `sidebar.css` (391). For each: is it one coherent thing, or several?
- **Undersized//thin modules.** `identity/db.py` (10 lines), `routes/persons.py`
  (13), `routes/stats.py` (14). Worth merging?
- **File names.** e.g. `pgvector-db/data_schema_with_types.md`,
  `identity_resolution.py`, `cas_views.py`, `videoLoader.js`. Also: JS is
  camelCase, Python is snake_case — confirm that stays as the per-language norm.
- **Folder/package layout.** `queries/` vs `routes/` vs `query_agent/` in the
  webapp; `parsers/` in the importer. Does the grouping still hold?
- ~~**`pgvector-db`'s shape.**~~ **Resolved:** no `src/`, no `tests/`. It stays
  as it is. It may still gain a `docs/` and a README in Phase 7 like the others.
- **⚠️ The compose project rename needs a volume migration.** `name:
  duui-bundestag-stack` in `docker-compose.yml` is what Compose derives volume
  names from, so changing it re-points `db_data` and `video_media` at new, empty
  volumes — orphaning a database that currently holds 375k rows. The data is
  reproducible (§7), so this is lost time rather than lost work — but it must be
  a **decision**, not a surprise: choose explicitly between migrating the volume
  (`pg_dump`/restore, or a volume-to-volume copy) and re-importing, and do it in
  the same commit as the rename. See [phase-0-baseline.md](phase-0-baseline.md)
  §0.2(a).
- **Stale name purge.** `DUUI` stays as the prefix; `bundestag` is removed or
  renamed *where it makes sense* (decided 2026-08-22). Read each of the 18 files
  rather than running a global replace: some occurrences are the dead project
  name (`duui-bundestag-stack`, the README title) and must go, while others
  correctly describe **the corpus**, which genuinely is Bundestag material.
  Also: the sibling directory `duui_bundestag_pipeline/` and the root
  `.github/workflows/ci.yml` that targets it belong to the *predecessor* project
  and are out of scope — do not rename or "fix" either. Decide the canonical
  project name; execute in 3b.

**3b. Execute** — renames and moves via `git mv` so history follows; suites
green after each. Nothing in this phase changes behaviour.

**Exit:** decisions recorded; structure final; tests green; no `bundestag`
references left outside historical context.

---

### `[x]` Phase 4 — Dependencies, runtime versions, tooling

**Why here:** before the doc rewrite, because bumping Python changes what the
code may use (and therefore what gets documented), and because a formatter
enforces part of the style guide mechanically instead of by hand review.

- **Python version.** Currently 3.12 in all three images. Evaluate 3.13/3.14:
  what is gained, what breaks, and whether `psycopg2-binary` / `dkpro-cassis` /
  `fastapi` have wheels. Answer explicitly whether the bump is worth it — "stay
  on 3.12, here is why" is a valid, documentable outcome.
- **Postgres + pgvector.** `pgvector/pgvector:pg16` → pg17/pg18? Note this
  affects an existing data volume; migration cost is part of the decision.
- **Direct dependencies.** Per sub-project: current floor vs. latest, whether
  anything is unused, whether anything used is unlisted.
- **Pinning strategy.** Today: `>=` floors, no upper bounds, no lockfile — two
  builds a month apart are not the same build. Decide the *strategy* here
  (floors vs. upper bounds vs. full lock); **generating the lockfiles themselves
  is deferred to Phase 9** by decision, since they are only meaningful once every
  dependency is final.
- **Formatters, linters and checkers — the full roster is in §6** (decided
  2026-08-22) and covers every language and file format in the repository:
  Python, JavaScript, CSS, HTML, SQL, Dockerfile, `docker-compose.yml`, YAML,
  the workflow files, and Markdown including a link checker. Configure all of
  them here and wire them into the CI workflow. This is what stops the style
  guide from decaying, and it shrinks Phase 5 by taking formatting off the table
  entirely. Config must encode the Phase 1 style guide (line width, quote style,
  import order).
- **A `package.json` for the JS-side tooling.** Node in CI is permitted
  (§7); this single dev-dependency file carries `tsc`, `eslint`, `prettier`,
  `stylelint` and `html-validate`. It is dev-only — nothing about the frontend's
  no-build-step deployment changes, and the shipped files stay byte-identical to
  the source.
- **A lint CI workflow** (decided 2026-08-22), at `<git-root>/.github/workflows/`
  — the only place GitHub Actions reads from — scoped with `paths:` filters to
  `duui-video-emotion-visualization/**` so no sibling project triggers it. Model
  it on the existing `ci.yml`, which already scopes itself to one subproject the
  same way, and filter *both* triggers (`ci.yml` does not filter
  `pull_request:`). Lint needs no database and no application dependencies, so
  keep the job free of them. See the note in §7 for the full rationale.
  **Its header comment must carry the "moving this project breaks the CI"
  warning** from §7 — the workflow does not travel with the project, and it
  fails silently rather than loudly when left behind.
- **A type checker in that workflow** (decided 2026-08-22): `mypy` (or
  `pyright`) over all three Python sub-projects, configured **lenient at the
  start and strict by the end** — see the ratchet note in §7. Alongside it,
  `tsc --checkJs --noEmit` over the JSDoc-annotated frontend (decided
  2026-08-22).
- **`requirements-dev.txt`** — review against what the suites actually import.

**Exit:** versions decided (bump or documented no-bump); tooling configured;
everything still builds and passes.

---

### `[x]` Phase 5 — In-file documentation rewrite

**Why here:** structure and versions are settled, style is defined, facts are
verified. Now the prose can be written once.

Sub-project by sub-project, module by module, against the Phase 1 guide and the
Phase 2 ledger. Per file:

- Module docstring/header: what this file is for, what it owns.
- Every function/class/method: purpose, parameters, return, raises, and any
  non-obvious behaviour.
- **Full type annotations**, added in the same pass as the docstrings — the two
  belong together, since the annotation is what lets the docstring stop
  describing types. **Python** gets real annotations; **JavaScript** gets JSDoc
  `@param`/`@returns` types plus `// @ts-check`, which is the same discipline
  expressed in comments. **Tighten the type checker on each sub-project as that
  sub-project is finished**, rather than leaving everything lenient and flipping
  one global switch at the end. `mypy` supports per-module strictness, so a
  completed sub-project is held to the strict setting immediately and cannot
  regress while the next one is in progress. By the time Phase 5 ends, strict is
  already on everywhere and the "flip to strict" step is a formality rather than
  a cliff.
- Delete every comment that restates the code, every stale comment, every
  rationale essay that belongs in `docs/`.
- Correct everything the fact ledger flagged as wrong.
- Also in scope, easy to forget: SQL (`schema.sql`), `Dockerfile`s,
  `docker-compose.yml`, `.dockerignore`s, `pyproject.toml`s,
  `requirements*.txt`, `.env.example`, CSS, `index.html`, and the test files.
- Also: user-facing strings — log lines, error messages, CLI output. They are
  documentation too and share the terminology glossary.
- **Duplicated files get matching documentation.** Where two sub-projects hold
  near-identical code (`job_runs.py` above all, also `db.py` and parts of
  `config.py`), their comments and docstrings must say the same thing in the
  same words, differing *only* where the behaviour genuinely differs — and
  where it does differ, saying so explicitly. Divergent prose over identical
  code is how a reader is misled about which copy they are looking at. Diff the
  pairs as a verification step, not just as a starting point.

Suggested order (smallest first, to shake out the style guide on cheap files
before committing to the big ones): `pgvector-db` → `global-identity-linker` →
`cas-to-postgres-importer` → `webapp` (backend, then frontend JS, then CSS).

**Checkpoint after the first sub-project:** review the result against the style
guide, amend the guide if it did not survive contact, *then* continue.

**Exit:** every code file documented to the guide; no AI-boilerplate left.

---

### `[x]` Phase 6 — Test audit

**Why here:** after the structure settles (test paths follow module paths) and
after Phase 5, which reads every line of source and is the cheapest possible
moment to notice what is untested.

- **Redundancy:** overlapping assertions, tests that only re-test the framework,
  the four `contrast`/`cvd`/`markup`/`stylesheet` suites' mutual overlap.
- **Gaps:** no test module imports `query_agent/agent.py`,
  `query_agent/schema_context.py` or `queries/persons.py`, and the importer's
  individual `parsers/*` modules are only exercised indirectly through the
  pipeline; there are no frontend JS tests at all. Confirm and decide which gaps
  are worth closing.
- **Accessibility checks → proper tests** (goal set 2026-08-22). The four files
  are in two different situations:
  - `contrast_check.py`, `cvd_check.py`, `markup_check.py` are **already**
    exercised by pytest — they are support libraries that `test_contrast.py`,
    `test_palette.py`, `test_markup.py` and `test_stylesheets.py` import. Nothing
    needs converting. What they need is for that relationship to be *obvious*:
    a naming/placement convention (e.g. `tests/support/`) that distinguishes a
    helper module from a test module, plus a note in each header naming the test
    modules that drive it. Also confirm they are additionally runnable standalone
    as `python3 tests/contrast_check.py`, as `webapp/docs/accessibility.md`
    claims — and if so, document that as a supported second entry point rather
    than an accident.
  - `a11y_browser_check.js` is the genuinely manual one: axe-core over five
    application states plus a keyboard sweep, three of those states only
    existing after JS has run. Automating it needs a headless browser
    (Playwright or Puppeteer) and a vendored axe-core, i.e. **adding a Node
    toolchain to a repo that is Python end to end** — the file's own header says
    it was written for console paste precisely because no such toolchain exists,
    and that it drops into `evaluate()` unchanged if one is added. That cost is
    the decision; see open question 11. If the answer is yes, this becomes the
    largest single item in Phase 6 and should probably be its own phase.
    If no, it stays manual — but its instructions and its expected-results
    baseline must be accurate and easy to follow.
- **Make the DB-dependent tests runnable without a pre-existing Postgres**
  (decided 2026-08-22). Today they skip silently, so a suite can report green
  having run a fraction of its assertions — a weaker signal than it appears.
  Constraint on the approach: these tests exercise real SQL against the real
  schema, including pgvector operators, so SQLite is not an option and mocking
  the driver would leave them asserting nothing worth asserting. **Decided:
  testcontainers** — a throwaway Postgres per run, which makes Docker a
  test-environment requirement (accepted 2026-08-22). Any remaining skip must be
  loud rather than silent.
- **Draw the boundary between `html-validate` and `markup_check.py`** (§6):
  the linter owns HTML *validity*, the test suite owns *accessibility
  semantics*. Write that down in both, or each will slowly grow into the other.
- **No shared test helpers across sub-projects** either (§1). If two suites need
  the same fixture, each keeps its own copy, documented identically.
- Document how to run each suite, in that sub-project's README (written in
  Phase 7).

**Exit:** redundant tests removed, agreed gaps closed, tools relocated, suites
green.

---

### `[ ]` Phase 7 — READMEs and `docs/`

**Why last:** it describes the finished state, and the finished state does not
exist until Phase 6 closes.

Built to the Phase 1b documentation map:

**Audience, in priority order** (decided 2026-08-22) — binding on every README:
**(1) a user who wants to run the thing**, **(2) a developer, or anyone trying
to understand the structure**. Depth beyond that belongs in `docs/`, which the
READMEs link to. When the two audiences conflict, the user wins: usage
instructions come before architecture.

- **Root `README.md`** — as short as possible while still covering the whole
  project: what it is, the four parts and how they fit, prerequisites, the
  one-path quickstart, and links onward. Everything else moves out. Target: a
  page you can read in two minutes, down from 968 lines.
- **`webapp/README.md`**, **`cas-to-postgres-importer/README.md`**,
  **`global-identity-linker/README.md`**, **`pgvector-db/README.md`** — each
  self-contained for someone working on only that part: purpose, how to run it
  standalone, configuration, how to test it, links to its `docs/`.
- **`docs/` at root** — cross-cutting detail: architecture, the database schema,
  configuration reference, operations, the style guide, the decision records
  from Phases 3 and 4.
- **`<sub-project>/docs/`** — detail belonging to exactly one part. Fold the
  existing `webapp/docs/` accessibility set in here (and fix the broken path in
  `a11y-ci.yml`).
- Kill the `.env.example` ↔ README configuration duplication: one of them owns
  it, the other links.
- **Use the short form for running the two batch jobs** (verified 2026-08-22 on
  Compose 5.5.0):

  ```bash
  docker compose run --rm cas-to-postgres-importer
  ```

  Modern Compose activates a service's own profile when the service is named
  directly, so `--profile import` / `--profile identity` is **redundant for
  `run`**. Make the short form the default everywhere the docs show these
  commands — it is less to type and one less concept to explain.

  Two things the docs must still say, though:

  - **`--profile` is required on older Compose versions**, where `run` did not
    auto-activate. Mention it as a fallback rather than the default: "if your
    Compose does not recognise the service, add `--profile import`."
  - **`--profile` is still required for `up`**, which operates on a set of
    services rather than a named one. The shorthand applies to `run` only.

  Explain *why* the two jobs are profiled at all, since that is the part a
  reader cannot infer: the importer writes to the database and the linker wipes
  and recomputes every global person, so neither may run as a side effect of
  `docker compose up`.
- **Decide what happens to `pgvector-db/data_schema_with_types.md`.** It is not a
  stale copy of the schema — it is the *design* document mapping UIMA CAS types
  to tables, and it declares itself as such. It is broadly accurate and states
  most of its own divergences. Two things are wrong with it regardless of that
  decision: it is written in mixed German and English (Phase 1 settled on US
  English), and it specifies `FusedEmotion` / `EmotionFusionReference` types that
  have no tables and no importer support. Consider a test that fails when the
  design and `schema.sql` diverge.
- **Update `webapp/docs/a11y-ci.yml`** — fix the dead `duui-bundestag-stack/…`
  path, and correct its header, which currently justifies leaving it off with a
  claim that is false: the repository *does* have CI, and a `paths:`-scoped
  workflow does not touch sibling projects. State the real reason (a deliberate
  choice) and what activating it would involve. Correct but inert, rather than
  wrong and inert. Do **not** activate it.
- **Font attribution.** A short note that Oxanium / Roboto / Ubuntu Mono are
  third-party, under OFL/UFL, with their license files alongside them.
- **`tests/` at the project root needs its own README.** It holds no tests — the
  four sub-projects do. It holds the *runners*: `Dockerfile.tests`,
  `Dockerfile.lint`, `run-tests.sh`, `run-lint.sh`, `ensure_test_db.py` and
  `check_links.py`. A directory called `tests` that contains no tests, sitting
  beside four directories that do, needs one paragraph saying so.
- **Document where the CI workflow lives and why it is outside the project**,
  and carry the §7 portability warning into the root `README.md` (or the docs
  page it links to) and anywhere the project layout is described.
- Every cross-reference verified to resolve.

**Exit:** the doc set matches the map; no duplicated ownership; every link works.

---

### `[ ]` Phase 8 — Final sweep

- Read the whole doc set start to finish as a new reader would. Fix what only
  becomes visible at that scale: contradictions, gaps between documents,
  terminology drift.
- Verify from scratch: fresh clone → quickstart → working stack, following only
  the new docs. Whatever the docs fail to say, this finds.
- Full test run; full `docker compose` build; confirm the lint workflow fires on
  a change inside this project and stays silent on one outside it.

---

### `[ ]` Phase 9 — Lockfiles, then changelogs

**Why last:** both were explicitly deferred to the end (decided 2026-08-22), and
both are only meaningful once nothing else will move. A lockfile generated
mid-pass is stale by the next phase; a changelog written before the work settles
describes a state that never shipped.

**9a. Lockfiles for the containers** — generate per sub-project, to the pinning
strategy chosen in Phase 4, once every dependency is final. Verify each image
still builds from its lockfile, and document how to regenerate one.

**9b. Changelogs — the very last step of the whole pass.**

- One `CHANGELOG.md` per sub-project, covering changes to that sub-project.
- A root `CHANGELOG.md` that references the four sub-changelogs rather than
  restating them.
- Open: start fresh from the current state, or reconstruct from git history; and
  whether entries carry version numbers (implying a versioning scheme) or dates.
  See open question 2.

**Exit:** lockfiles build reproducibly; changelogs in place; this file closed
out — phases marked done, decision records archived.

---

## 5. Cross-cutting rules

- **Branch layout.** Everything lives under one `code-cleanup/` namespace:
  - **`code-cleanup/main`** — the integration branch. Every phase merges here.
  - **`code-cleanup/phase-<N>`** — one per phase, branched off
    `code-cleanup/main`, merged back with `--no-ff` when the phase closes.
  - `code-cleanup/main` merges into `main` **once, at the very end** of the
    whole pass.

  The namespace requires that no branch is literally named `code-cleanup`: git
  stores refs as file paths, so a `code-cleanup` *file* and a `code-cleanup/`
  *directory* cannot coexist. This applies on `origin` as well as locally, which
  is why the old remote `code-cleanup` branch is deleted rather than kept.
  `code-cleanup` reaches `main` only at the end of the whole pass. One
  commit per logical step; never mix a rename with a rewrite in the same commit,
  as that makes the diff unreviewable.
- **Every commit message starts `Phase <N>:`**, followed by a lowercase
  summary — `Phase 3: rename the importer package`. Without it the log gives no
  way to tell which phase a change belongs to, and the phases are the only
  structure this work has. It applies to every commit in a phase branch, not
  only the ones that touch the plan.
- **No AI attribution, anywhere.** Commits carry no `Co-Authored-By: Claude`
  trailer, no "generated with" line, and no "written or assisted by AI" note —
  not in commit messages, not in code comments, not in documentation. The commit
  author is the repository owner alone. This applies to every file this plan
  produces.
- **Tests green before every commit.** A doc-only pass has no excuse for a red suite.
- **Existing documentation and comments are not evidence.** Nearly every comment
  in this codebase was **written by AI, not by the author** — the frontend style
  and accessibility work is the only exception. They are guesses that read like
  knowledge, and they may be simply wrong.

  **Never say so in the repository.** This paragraph, and this plan, are the only
  place the provenance is recorded. In every committed file — documentation,
  comments, commit messages, the legacy quarantine notice — describe such text as
  *legacy*, *outdated*, *unverified*, or *possibly wrong*. Never as AI-written,
  AI-generated, or machine-authored. The practical instruction is identical; only
  the attribution is dropped, and it is dropped everywhere.

  So they carry no authority for *anything*: not for what the code does, and
  **not for why it does it**. An existing comment stating a reason is not a
  reason; it is an unsourced claim. Verify it independently or discard it —
  never carry it forward just because it is already written down.

  **The code, the schema, the database and the tests are the only sources of
  truth.** Write only what they can verify. Where something matters and cannot
  be verified, **record the uncertainty and ask** — never invent, never infer
  from plausibility, never assume a previous comment got it right. Documentation
  written *after* this plan began and explicitly verified may be relied on;
  nothing earlier may. Log discrepancies in the fact ledger (Phase 2) rather
  than quietly correcting them in passing.
- **A found bug stops the work.** Note it. If the correct fix is clear and
  sensible, implement it and document both the bug and the fix. If it is not
  clear, **interrupt and ask for guidance** — do not continue past a known bug
  and do not guess.
- **Unattended runs have to stop and ask.** This is not a soft preference and it
  is not waived by nobody being at the keyboard. An autonomous or scheduled run
  that hits a decision it cannot make correctly **halts and waits**, however much
  work remains. Stopping with a question is always the right outcome; guessing
  in order to keep moving is always the wrong one. The same applies to any
  ambiguity that would change the result, not only to bugs.
- **No incidental behaviour changes** outside Phases 4, 6 and the bug rule
  above. A documentation pass that silently changes behaviour is not reviewable.
- **Sub-projects stay standalone.** No file is shared between them — no common
  package, no cross-project import, no symlink. Each of the four must be
  understandable, buildable and testable on its own. Duplication is the accepted
  cost.
- **Duplicated code carries duplicated documentation.** Where the same code
  exists in two sub-projects, its comments and docstrings must match word for
  word, except where behaviour genuinely differs — and there, the difference is
  stated explicitly. The pairs get diffed as a check, not just as a starting
  point.
- **Never describe the current corpus in documentation.** No row counts, id
  ranges or per-table totals in a comment, a docstring, a `docs/` page or a
  README — in **Phase 5, Phase 7, and any later documentation work**. Those are
  measurements of one database on one day; they go stale on the next import, and
  a reader cannot tell a stale number from a live one. Write the property that
  holds whatever is loaded. Measurements stay in the phase records, where they
  are evidence for a decision rather than a claim about the software. Recorded as
  rule 4 in the style guide.
- **Upgrade steps go in the plan, not in the documentation.** Where a phase
  changes something an existing deployment would have to fix by hand — a volume
  that needs chowning, a database that needs recreating — record it in that
  phase's file and nowhere else. **Nobody but the project owner runs this
  software until the whole plan is finished**, so a migration note in `docs/` is
  addressed to a reader who does not exist, and would have to be re-checked
  against the finished state anyway. Phase 7 decides what, if anything, survives
  into `docs/operations.md`.
- **`docs/todo.md` is not part of this cleanup.** It collects work to do
  *afterwards*, and nothing in it is in scope for any phase here. Entries are
  added **only when the project owner asks for one** — never from a passing
  observation, and never because something looks like it needs doing. The file
  itself deliberately does not say any of this; it is recorded here instead, so
  the file reads as a plain to-do list. Phase 7 gives it a proper form.
- **Terminology trap: "Phase 0" is overloaded.** `webapp/docs/accessibility.md`
  and `webapp/docs/a11y-baseline/` number their own phases 0–6. Those are the
  **accessibility remediation** phases from before this pass and have nothing to
  do with this plan's Phase 0. Both sets are correct in their own context; do not
  renumber either, and disambiguate when referring to one in prose.
- **Decisions get written down**, including the ones that end in "no change".
  A documented "we stayed on Python 3.12 because X" prevents the question being
  re-asked in six months.

---

## 6. The linter and checker roster

No open questions remain. This section is the agreed tooling list, to be
configured in Phase 4 and wired into the CI workflow. **Every language and file
format in the repository is covered** — the roster below was built by
enumerating what actually exists, not by listing familiar tools.

| Covers | Tool | Notes |
| --- | --- | --- |
| **Python** — format + lint | `ruff` | Replaces black/isort/flake8. Config encodes the Phase 1 style guide. |
| **Python** — types | `mypy` (or `pyright`) | Lenient → strict via the ratchet in §7. |
| **JavaScript** — lint | `eslint` | |
| **JavaScript** — types | `tsc --checkJs --noEmit` over JSDoc | Checker only, emits nothing; source ships unchanged. |
| **JS / CSS / Markdown** — format | `prettier` | One formatter across all three. |
| **CSS** — lint | `stylelint` | |
| **HTML** — validity | `html-validate` | For `index.html`, the only HTML file. See the overlap note below. |
| **SQL** | `sqlfluff` | `pgvector-db/schema.sql`, with the Postgres dialect. |
| **Dockerfile** | `hadolint` | All four Dockerfiles. See the finding below. |
| **`docker-compose.yml`** | `docker compose config --quiet` | The built-in validator — no new tool, catches schema and interpolation errors. |
| **YAML** | `yamllint` | Covers `docker-compose.yml` **and** the workflow files themselves. |
| **GitHub Actions workflows** | `actionlint` | Validates expressions, action refs, and shell inside `run:` blocks. Worth having the moment we author a workflow. |
| **Markdown** — lint | `markdownlint` | |
| **Markdown** — links | `lychee` (or `markdown-link-check`) | **See below — this one earns its place.** |

### Notes on four of them

**The link checker is the highest-value item in the table.** Phase 7 already
carries "every cross-reference verified to resolve" as an exit criterion, and
Phase 7 is precisely where a web of new links appears: root README → four
sub-READMEs → root `docs/` → four `<sub-project>/docs/`. Checking that by hand is
tedious and gets skipped; checking it mechanically is one CI job. It also keeps
working afterwards, which is the point — the current 8 markdown files are about
to become considerably more.

**`hadolint` has already found something, without being run.** None of the four
Dockerfiles has a `USER` directive, so **all four containers run as root**. That
is a real finding rather than a style nit, and it is a *behaviour* change to fix,
so it falls under the bug rule in §5: note it, and if the fix is clear
(add a non-root `USER`, adjust file ownership) implement and document it —
otherwise ask. Flagged here so it is not discovered and quietly skipped.

**`html-validate` overlaps with existing tests, and that is fine** as long as the
boundary is written down. `markup_check.py` / `test_markup.py` already inspect
`index.html`, but for *accessibility semantics* — landmarks, labels, heading
order. An HTML linter checks *validity* — unclosed tags, bad nesting, duplicate
ids. Different questions about the same file. Phase 6 should state which tool
owns which question so neither grows into the other.

**Node in CI is now accepted** (decided 2026-08-22) for `tsc`, and that same
`package.json` carries `eslint`, `prettier`, `stylelint` and `html-validate` at
no additional setup cost. Note what this means: the "no Node toolchain" position
now has exactly one remaining consequence — the a11y browser tests stay manual
(§7 item 11) because *those* need a browser download, not because Node is
unavailable. Keep that distinction visible in the docs, or the manual procedure
will look like an oversight later.

---

## 7. Decisions log

Answers given, with the date. The phases above are already updated to match;
this is the index.

| # | Question | Decision (2026-08-22) |
| --- | --- | --- |
| — | Sharing code between sub-projects | **Never.** Each stays standalone; duplication is accepted. Rule in §1 and §5. |
| — | The `job_runs.py` duplication | Keep both copies; make their **documentation match**. Moves from Phase 3 to Phase 5. |
| — | `pgvector-db` missing `src/`/`tests/` | Correct as-is. Database image, exempt from the inner-structure rule. |
| — | The four accessibility check files | Three are already pytest support libraries and need only clearer naming. See item 11. |
| — | `src/main/` package name | `main` or `importer`, both fine. Recommendation: **`importer`** — `backend` and `identity` both describe what they are; `main` does not. |
| — | Python type hints | **Yes — adopt fully, and check them in CI.** Lenient at first, **strict once this plan is complete.** See the ratchet note below. |
| — | JavaScript types | **Yes — JSDoc annotations, checked in CI** with `tsc --checkJs --noEmit`. **Node in CI is explicitly permitted as an exception** for this. No TypeScript, no build step: the source files ship exactly as written. |
| — | Linters for Dockerfile / compose / YAML / HTML / Markdown | **Yes** — full roster in §6. |
| — | Branch layout | **`code-cleanup/main`** integrates; **`code-cleanup/phase-<N>`** per phase, merged back with `--no-ff`; `main` only at the very end. No branch may be named plain `code-cleanup` — see §5. |
| — | Commit attribution | **None.** No AI/Claude attribution in commits, comments or docs — see §5. |
| — | Authority of existing comments | **None.** Unverified and possibly wrong, including about intent. Verify independently or discard; ask rather than assume. Only the frontend style/accessibility material reflects real decisions, and it is kept because it is test-verifiable. |
| — | How provenance is described | **Never name AI as the author anywhere in the repository.** Say *legacy*, *outdated*, *unverified*, *possibly wrong*. Recorded in §5 and nowhere else. |
| — | The root README and `data_schema_with_types.md` | **Quarantined to `docs/legacy/`**, not verified and not rewritten now. A short, true README replaces the root one. Phase 7 uses the quarantined files as a topic checklist, moves the database content into `docs/database.md`, then deletes them. |
| — | `/api/stats` (D9) | **Keep for now**, and keep it registered as a discrepancy. |
| — | `docs/todo.md` | A scratchpad for **post-cleanup** work — see §5. |
| — | `docs/` skeleton | **Built in Phase 1**, not Phase 7, so Phase 5 has real pages to move rationale into. Phase 7 becomes an editing job. |
| — | Where the plan lives | **`docs/plan/`**, with this file as `README.md` and one `phase-N-*.md` per phase. Cross-cutting content stays here; per-phase detail is split out. |
| — | The live test data | **Disposable and reproducible.** The running stack is a test stack. Lowers the severity of the Phase 3 volume hazard from data loss to wasted time — it still needs a deliberate decision, not an accident. |
| 1 | `CLAUDE.md` | **You will run `/init` after this plan is finalized.** Not a plan deliverable. It should be pointed at the Phase 1 style guide once that exists, so the two do not drift. |
| 2 | Formatters and linters | **Yes**, for every language in the repo: Python, JavaScript, CSS, SQL, Markdown. Configured in Phase 4, and enforced by the CI workflow below rather than by habit. |
| 3 | `webapp/docs/a11y-ci.yml` | **Update it, do not activate it.** Fix the broken `duui-bundestag-stack/…` path and anything else stale, so it is correct-but-inert rather than wrong-and-inert. Its header must say plainly that it is deliberately not active and what turning it on entails. |
| 4 | The `bundestag` name | **Remove or rename where it makes sense; `DUUI` stays as the prefix.** Note the nuance that makes this a judgement call and not a `sed`: some occurrences are the *stale project name* (`duui-bundestag-stack`, the README title) and must go, while others legitimately describe *the corpus*, which really is Bundestag material. Each of the 18 files gets read, not pattern-replaced. |
| 5 | `LICENSE` | **Not needed.** The project is internal-only, the images are not published, and the bundled fonts already ship their OFL/UFL files. Nothing to do — see the note below this table. |
| 6 | Lockfiles | **Created last** — after all dependency decisions are final. Moved out of Phase 4 into Phase 9. |
| 8 | Schema docs | `schema.sql` is the truth; `data_schema_with_types.md` gets rewritten from it. Generalized into a project-wide rule — see §5, "existing documentation is not evidence." |
| 9 | Documentation language | **US English** throughout. Into the style guide, along with a spell-check target. |
| 10 | Changelogs | **Yes** — one per sub-project, plus a root `CHANGELOG.md` referencing them. **The very last step of the whole pass** (Phase 9). |
| 11 | `a11y_browser_check.js` | **Stays a manual procedure.** No Node toolchain. Its instructions and expected-results baseline must be accurate and easy to follow. |
| 12 | README audience | **Primary: a user — how to use it.** Secondary: developers, or anyone wanting to understand the structure. Deeper developer material lives in `docs/`, and the READMEs link there. This ordering is binding on Phase 7. |
| 13 | Prose depth | **Historical "how this came to be" material is removed or moved into a `docs/` file.** Where extra depth prevents genuine confusion, keep it. Otherwise: short — but still accurate, consistent, and correctly placed. |
| 14 | What "root" means | **`duui-video-emotion-visualization/`.** The directory above is just a container for unrelated things. Root README, root `docs/`, root `CHANGELOG.md` all live here. |
| 15 | Bugs found mid-pass | **Note it and stop.** If the fix is clear and sensible, implement it and document it. If not, interrupt and ask. Never continue past a known bug. Replaces the old "log, do not fix" rule in §5. |
| 16 | DB tests without Postgres | **Yes.** Docker as a test-environment requirement is acceptable, so **testcontainers** is the approach: a throwaway Postgres per run, real SQL against the real schema, no database the developer has to set up. |
| — | Python / Postgres version bumps | **Deferred to Phase 4's own planning**, not decided now. Phase 4 evaluates and recommends. |
| — | Linting in CI | **Yes — add a lint workflow at the git root, scoped to this project only.** See the note below, including the portability reminder. |
| — | Changelog scope | **Deferred to Phase 9's own planning.** |
| — | README scope | **Deferred to Phase 7's own planning** — except the root README, which is confirmed as a **two-minute read**. |
| — | Stop-and-ask in unattended runs | **Confirmed, and binding.** An unattended run *has to* stop and ask when the situation calls for it. Halting early is always preferable to guessing. |

### On type-checking strictness — the ratchet

"Lenient at first, strict once the plan is done" is the decision. **How** it gets
there matters, because there is a good way and a bad way:

- **Bad:** leave the checker lenient everywhere for the duration, then flip one
  global switch at the end. That converts the last step of the plan into a wall
  of several hundred errors, arriving exactly when the appetite for the work is
  lowest — and nothing stops a finished sub-project from regressing in the
  meantime.
- **Good — do this instead:** Phase 5 already proceeds one sub-project at a time.
  Tighten the checker on each sub-project **as that sub-project is finished**.
  `mypy` supports per-module configuration, so `global-identity-linker` can be
  held to strict while `webapp` is still lenient. Each completed piece is then
  locked in and cannot regress while the next one is being worked on.

Under the ratchet, strictness arrives incrementally and the final "make it
strict" step is a formality — the config already says so everywhere. Order the
work smallest sub-project first (as Phase 5 already does) and the settings are
shaken out on cheap files before the webapp.

The end state, to be explicit: **strict type checking on all Python, enforced by
CI, once this plan is complete.**

### On licensing (item 5) — resolved

The project is internal-only and the images are not published, so **there is
nothing to do.** Recorded for the day that changes:

- **The bundled fonts already comply.** Oxanium and Roboto ship under the SIL
  Open Font License, Ubuntu Mono under the Ubuntu Font Licence; both require the
  license text to travel with the fonts, and `OFL.txt` / `UFL.txt` already sit
  beside each font file. A short attribution note in the webapp docs remains
  worthwhile for discoverability (Phase 7), but it is courtesy, not obligation.
- **If the images are ever published**, `psycopg2-binary` is LGPL and the Debian
  base of `python:3.12-slim` carries its own set — redistribution is what
  triggers those obligations, and a `THIRD-PARTY-NOTICES.md` is the tidy answer.
  Not now.

### On linting in CI — yes, and it is the established pattern here

**It works, and the repository is already doing exactly this.** GitHub Actions
only reads workflows from `<git-root>/.github/workflows/`, never from a
subdirectory — and that directory already exists and already holds a
project-scoped workflow. `ci.yml` scopes itself to one subproject with
`defaults: run: working-directory: duui_bundestag_pipeline`. A second workflow
for this project follows the same shape:

- `paths:` filters on `duui-video-emotion-visualization/**` so it only fires
  when *this* project changes — sibling projects never trigger it and never
  consume minutes for it. Note that `ci.yml`'s `pull_request:` trigger carries
  no `paths:` filter and so runs on every PR; the new workflow should filter
  both triggers, or it will inherit that behavior.
- `working-directory: duui-video-emotion-visualization` for every step.
- A lint job needs neither the database nor the application dependencies, so it
  is fast and cannot be broken by an unrelated dependency problem.

**One wrinkle worth stating plainly:** §7 item 14 defines "root" as
`duui-video-emotion-visualization/`, but this file physically *cannot* live
there. It is the one deliverable of this plan that sits outside the project
directory. The project's own docs should say where it is and why.

> #### ⚠️ Reminder: moving this project breaks the CI
>
> Because the workflow lives outside the project directory, **it does not travel
> with the project.** If `duui-video-emotion-visualization/` is ever moved,
> extracted into its own repository, or copied elsewhere, the lint workflow is
> left behind and has to be set up again from scratch — and, worse, it fails
> silently: nothing errors, CI simply stops covering the code. The same applies
> to every `paths:` filter and `working-directory:` in it, which are written
> relative to the *current* git root and will all be wrong at the new location.
>
> This warning is not to live only in this plan. It must appear in three places
> that a person will actually encounter:
>
> 1. In the workflow file's own header comment.
> 2. In the root `README.md` (or the docs page it links to for CI).
> 3. Alongside anything else describing the project's layout.
>
> If the project ever *does* become its own repository, the fix is simple —
> the workflow moves to that repository's own `.github/workflows/` and the path
> prefixes are dropped — but somebody has to know to do it.

**And it retires a false premise.** `webapp/docs/a11y-ci.yml` was left inert on
the reasoning that the repository "has no CI at all" and that adding a workflow
"introduces GitHub Actions to all" the sibling projects. Both halves are wrong:
Actions is already present and already scoped to a single subproject. That does
not overturn your decision to leave the accessibility workflow inactive
(item 3) — but the *stated reason* must be corrected rather than copied forward,
and once a scoped lint workflow exists, activating the accessibility one later
is a one-line decision rather than a new precedent.

Scheduling: the workflow is written in **Phase 4** alongside the linter configs,
and verified in Phase 8.

---

## 8. Progress log

| Phase | Status | Branch | Notes |
| --- | --- | --- | --- |
| 0 — Baseline | `[x]` | `code-cleanup` | Done 2026-08-22. **Green baseline = 150/150 on an empty DB.** 4 findings logged. Detail: [phase-0-baseline.md](phase-0-baseline.md). |
| 1 — Style guide + doc map | `[x]` | `code-cleanup/phase-1` | Done 2026-08-22. Style guide, glossary, doc map and `docs/` skeleton in place. Detail: [phase-1-style-guide.md](phase-1-style-guide.md). |
| 2 — Fact ledger | `[x]` | `code-cleanup/phase-2` | Done 2026-08-22. D1–D12 registered, contracts verified, legacy docs quarantined. Line-by-line reading deferred to Phase 5. |
| 3 — Structure | `[x]` | `code-cleanup/phase-3` | Done 2026-08-22. Renames, splits and groupings landed; corpus rebuilt and every row count matches Phase 0. |
| 4 — Dependencies | `[x]` | `code-cleanup/phase-4` | Done 2026-08-22. Python 3.14, Postgres 18, 13 checkers, CI and a pre-commit hook. |
| 5 — In-file docs | `[x]` | `code-cleanup/phase-5` | Done 2026-08-29. Every comment and docstring rewritten across all four sub-projects; every function annotated; `tsc` and a style checker added to the gate; E501 exemption removed. 15 false claims corrected. Detail: [phase-5-documentation.md](phase-5-documentation.md). |
| — Fix D4 | `[x]` | `code-cleanup/fix-d4-connect-timeout` | Done 2026-08-29. `connect_timeout` in `DB_CONFIG` across all three services, from `DUUI_DB_CONNECT_TIMEOUT` (default 10). The webapp now starts against an unreachable database instead of never listening. |
| 6 — Test audit | `[x]` | `code-cleanup/phase-6` | Done 2026-08-29. Coverage 48% to 83%; the importer's parsers and both job-run copies had none. Two of the outline's premises were found stale and dropped. |
| 7 — READMEs + docs | `[~]` | `code-cleanup/phase-7` | Plan drafted 2026-08-29; four questions open. Three `docs/` pages are still stubs and five READMEs do not exist. |
| 8 — Final sweep | `[ ]` | | |
| 9 — Lockfiles, then changelogs | `[ ]` | | |

---

## 9. Detailed phase plans

### Index

| Phase | Detailed plan | Status |
| --- | --- | --- |
| 0 — Baseline and safety net | [phase-0-baseline.md](phase-0-baseline.md) | `[x]` done |
| 1 — Style guide + doc map | [phase-1-style-guide.md](phase-1-style-guide.md) | `[x]` done |
| 2 — Fact ledger | [phase-2-ledger.md](phase-2-ledger.md) · [phase-2-modules.md](phase-2-modules.md) | `[x]` done |
| 3 — Structure | [phase-3-structure.md](phase-3-structure.md) | `[x]` done |
| 4 — Dependencies + tooling | [phase-4-tooling.md](phase-4-tooling.md) | `[x]` done |
| 5 — In-file documentation | [phase-5-documentation.md](phase-5-documentation.md) | `[x]` done |
| — Fix D4 (connect timeout) | [fix-d4-connect-timeout.md](fix-d4-connect-timeout.md) | `[x]` done |
| 6 — Test audit | [phase-6-tests.md](phase-6-tests.md) | `[x]` done |
| 7 — READMEs + docs | [phase-7-docs.md](phase-7-docs.md) | `[~]` plan drafted |
| 8 — Final sweep | *not yet written* | `[ ]` |
| 9 — Lockfiles, then changelogs | *not yet written* | `[ ]` |

**What goes where.** This file is the durable record: constraints (§1), the
starting state (§2), the phase overviews (§4), the cross-cutting rules (§5), the
tooling roster (§6), the decisions log (§7) and the progress table (§8). Those
are cross-cutting and must have exactly one home, so they are never duplicated
into a phase file.

Each `phase-N-*.md` holds that phase's step-by-step plan and its working notes
and results. They are written when the phase starts, not before. When a phase
finishes, its outcome is summarised in one line in §8 here; the full detail stays
in the phase file.
