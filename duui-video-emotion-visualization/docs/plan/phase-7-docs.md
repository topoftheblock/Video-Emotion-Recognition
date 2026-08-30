# Phase 7 — READMEs and `docs/`

Branch: `code-cleanup/phase-7`. The phase your original request pointed
at most directly: a README in each sub-project, a root README as short
as possible, and `docs/` for the detail.

---

## 7.1 What is already decided, and binding

This phase invents nothing. Two documents settle the shape, and both
are finished:

- **[`docs/README.md`](../README.md)** is the map. It states, per
  document, the audience, what it **owns**, and what it **must not
  contain** — that second column being what stops one explanation
  appearing in five places and drifting five ways. It also fixes the
  five rules that follow from it.
- **[`documentation-style.md`](../documentation-style.md)** governs how
  every line is written, and is enforced by `tests/stylecheck.py`.

**Audience, in priority order, binding on every README:** a user who
wants to run the thing, then a developer or anyone orienting. When they
conflict, the user wins — usage before architecture.

**The legacy documents are not a source.** `docs/legacy/` holds the
pre-rebuild README and design document. They are stale and largely
wrong, and nothing in this phase may take a fact from them. Confirmed
2026-08-29. They are not even a topic checklist: the topics come from
the code, the schema and the compose file, all of which can be checked.

## 7.2 Rules for this phase

The cross-cutting rules in [§5 of the plan overview](README.md) apply
unchanged, as do [documentation-style.md](../documentation-style.md) and
[glossary.md](../glossary.md). These are the additional ones this phase
needs, because it is the first that writes documents rather than
comments.

1. **`docs/legacy/` is not a source — not for facts, not for topics.**
   Nothing may be taken from it, and it is not read for what subjects a
   page should cover. Topics come from the code, the schema and
   `docker-compose.yml`.

2. **Never migrate a claim out of a legacy document.** If something
   there looks worth keeping, establish it from the code, the schema,
   the database or the tests, and write *that*. If it cannot be
   established, it does not go in. See §7.10 for the case that set this.

3. **Every command in every document gets run, not read.** A command
   that no longer works is this documentation's characteristic failure,
   and Phase 5 found several. A command that cannot be run in this
   environment is marked as unverified where it stands, or cut.

4. **Every variable is verified against the code that reads it.** Not
   against `.env.example`, not against the current README, and not
   against another document. Six of them are read only by
   `docker-compose.yml`; those are verified there, and the page says
   which layer reads each.

5. **Every path named in prose must exist.** The link checker covers
   Markdown links only. A path written as text — `webapp/src/backend/app.py`,
   `tests/run-lint.sh` — is checked by hand or by script.

6. **The map's "must not contain" column is a check, not advice.** Each
   finished page is read against its row in
   [`docs/README.md`](../README.md). A page that explains something
   another page owns is wrong even if what it says is true.

7. **No placeholder survives.** Every `<!-- … -->` outline comment and
   every "**Stub.**" banner is either replaced by prose or deleted with
   its heading. A heading with nothing under it is not a document.

8. **A section with nothing true to say is removed, not padded.** If a
   procedure does not exist, either establish and verify one, or say
   plainly that there is none. Neither invent one nor leave the heading
   empty.

9. **Terminology is checked, not remembered.** `tests/stylecheck.py`
   reads Markdown for prose width and em dashes but does **not** check
   the glossary in `.md` files. Terminology in the new pages is checked
   by hand against [glossary.md](../glossary.md) before each commit.

## 7.3 The starting state, measured

### `docs/` is four finished pages and four stubs

| Page | State |
| --- | --- |
| `README.md` (the map) | Finished |
| `documentation-style.md` | Finished, 405 lines |
| `glossary.md` | Finished, 242 lines |
| `database.md` | Substantial, 2 placeholders left |
| `architecture.md` | **Stub** — 42 lines, 6 placeholders |
| `configuration.md` | **Stub** — 33 lines, 5 placeholders |
| `operations.md` | **Stub** — 32 lines, 5 placeholders |
| `todo.md` | A shell, by design |

### Five READMEs do not exist

`webapp/`, `cas-to-postgres-importer/`, `global-identity-linker/`,
`pgvector-db/`, and `tests/` at the root. The last is the odd one: a
directory called `tests` that contains no tests, sitting beside four
that do. It holds the runners and the checkers.

### The root README is already close

64 lines, and the two-minute target is met. What it still needs is
small: the "documentation is being rebuilt" banner removed, links to
the five new READMEs, the short form for the batch jobs, and the note
about where CI lives.

### The variables, counted from the code

22 `DUUI_*` names are read by application code — a first count said 25,
which was three grep artifacts from names split across string literals
(`DUUI_DB_*`, `DUUI_TS_*`, `DUUI_GLOBAL_PERSON_*`). Six more appear only
in `docker-compose.yml` or `.env.example` and are read by nothing in
`src`, for 28 in all:

    DUUI_DB_HOST_PORT     DUUI_TEST_DB_NAME    DUUI_TEST_UID
    DUUI_VIDEO_STORE      DUUI_WEBAPP_HOST_PORT DUUI_TEST_GID

Those are Compose-level knobs — ports, volume names, the uid the test
container runs as. `configuration.md` owns every one of them, and must
say which layer reads each, because "grep the source" will not find six
of them.

## 7.4 The `a11y-ci.yml` item, re-checked

The outline says to fix a dead `duui-bundestag-stack/…` path and a
false "no CI" premise. Only half of that is still true:

- **The path is already correct.** Phase 3 repointed it;
  `duui-video-emotion-visualization/webapp` resolves today.
- **The premise is still false, twice over.** The header says "This
  repository has no CI at all" — the repository has two workflows, one
  of them added by Phase 4 for this very project. It goes on to argue
  that adding a workflow "introduces GitHub Actions to all of them",
  which the existing `paths:`-scoped workflow disproves by running only
  for this directory.

**The real reason turned out to be better than the one §7.4 expected.**
Not CI minutes: the file is simply **redundant**. Its five suites are
part of the project suite, and the project workflow already runs the
whole suite — `docker compose run --rm tests` — on every push and pull
request touching this directory. So the checks it would run are already
running. The header now says that, and says the file is kept for the
case where the accessibility checks ever need to run on their own.

The repository root does hold 13 sibling projects, so the *caution* is
reasonable even though the stated facts are not. Rewrite the header to
give the real reason — a deliberate choice not to spend CI minutes on a
browser download — and say what activating it would involve. **Do not
activate it.**

## 7.5 What Phase 5 and Phase 6 left owing

- `webapp/docs/a11y-verification.md` is titled "after Phases 1–5",
  meaning the accessibility remediation phases. Beside a cleanup effort
  with its own Phase 5, that is confusing. Retitle by what it records,
  not by when.
- `docs/todo.md` has one entry and an empty "Open" section. Decide
  whether it earns its place or folds into the plan.
- The two gaps Phase 6 left open — `query_agent/agent.py` coverage and
  the `routes/videos.py` payload path — belong in `todo.md` if it
  survives.

## 7.6 Found while writing — deferred by decision

**`schema.sql` is idempotent for its indexes and not for its tables.**
All 15 `CREATE INDEX` statements and the `job_runs` table are declared
`IF NOT EXISTS`. The other 13 `CREATE TABLE` statements are not, so
re-running the file against a populated database prints thirteen
`relation "…" already exists` errors. `psql` continues past them, so it
half-works: new objects are created, existing ones error.

I nearly documented a re-run as the way to apply a schema change, and
the run that checked it is what caught this. The page now says what
actually happens and recommends applying the specific statement instead.

**Whether this is a defect is not clear, so it is not being changed.**
The asymmetry has a plausible reason: `job_runs` is idempotent because
three services also create it, and the 13 tables only ever run on an
empty data directory, where nothing exists to collide with. Against
that, a file whose halves behave differently is a trap, and the errors
are alarming for something the documentation might tell you to do.

The argument for leaving it: without `IF NOT EXISTS`, re-running tells
you loudly that a table is already there. With it, a table whose *shape*
has changed is silently skipped, which is worse.

**Decided 2026-08-30: defer.** The question is what the file should be,
not a defect with an obvious fix, so it is recorded in
[`docs/todo.md`](../todo.md) to be settled later. The current behavior is
documented where it bites — [operations.md](../operations.md), under
upgrading the schema on an existing volume — and `schema.sql` is left
unchanged.

## 7.7 Steps

| # | Step |
| --- | --- |
| 1 | Answer §7.9 — done |
| 2 | `docs/architecture.md` — the four parts, the four shared contracts, and why no code is shared — done |
| 3 | `docs/configuration.md` — all 28 variables, each verified against the code or the compose file that reads it — done |
| 4 | `docs/operations.md` — everyday commands, importing, recomputing, schema upgrades on an existing volume, the Compose-rename hazard, backup, CI — done |
| 5 | Finish `docs/database.md`'s two placeholders — done |
| 6 | The four sub-project READMEs, to the map's five-question shape — done |
| 7 | `tests/README.md` — what the directory is, since it holds no tests — done |
| 8 | Root README — drop the banner, add the links, adopt the short `run` form, note where CI lives — done |
| 9 | `.env.example` — one-line gloss per variable, pointing at `configuration.md`; kill the duplication — done |
| 10 | Rewrite the `a11y-ci.yml` header (§7.4); retitle `a11y-verification.md` — done |
| 11 | Font attribution: Oxanium, Roboto and Ubuntu Mono are third-party, OFL/UFL, licenses alongside — done, in `webapp/README.md` |
| 12 | Delete `docs/legacy/` — its three live references are already gone (§7.10) — done |
| 13 | Verify — see §7.8 |

## 7.8 Verification

- Every checker green, including the link checker over a much larger
  web of links, and `stylecheck.py` over the new prose.
- **Every command in every document actually run.** Not read — run. The
  documentation's failure mode is a command that no longer works, and
  Phase 5 found several.
- **Every variable checked against the code that reads it**, and the
  six Compose-only ones checked against `docker-compose.yml`.
- The map's "must not contain" column enforced by reading each page
  against it: no page explains something another page owns.
- A first-run rehearsal from a clean state: follow the root README from
  `docker compose up -d` to a video playing in the browser, doing only
  what it says.

## 7.9 Questions, answered

1. **`docs/legacy/` is deleted** (2026-08-29). Its content is not used
   and is known to be unreliable; leaving it is a trap for the next
   reader. See §7.10 for what that cost.
2. **`docs/todo.md` stays**, and the work Phase 6 left open moves into
   it — so "what is left" has one address that is not the plan.
3. **`pgvector-db/README.md` is short**: what the image is, the pgvector
   version, that the schema runs only on an empty volume, and a link to
   `database.md`.
4. **The root README keeps a minimal configuration section**: the two
   input-path variables a first run with real data must set, and a link
   to `configuration.md` for the rest.

## 7.10 The three references into `docs/legacy/` — already removed

Found while planning, and dealt with immediately rather than left for
execution, because two of them cited the legacy document as **evidence
for a decision**. That is the one thing it may never be.

| File | Was | Now |
| --- | --- | --- |
| `cas/types.py` | "The design mapping (`docs/legacy/…`) specifies the bare `annotation.MetaData` type here" | States the hierarchy the code itself declares, and why narrowing the name would break later |
| `query_agent/schema_context.py` | Named it as one of three sources the semantics were cross-checked against | Names the two sources that can actually be checked — the parsers and a populated database — and tells the reader to check before trusting |
| `docs/database.md` | A paragraph distinguishing itself from it | Deleted; it existed only to make that contrast |

**The claim in `types.py` was verified rather than deleted**, because it
turned out to be true and checkable without the document:

- `INJECTED_FALLBACK_TYPES`, in the same file, declares
  `model.MetaData` extending the bare `annotation.MetaData`, and
  `model.HuggingfaceMetaData` extending `model.MetaData`. The comment
  had said both extend the bare type directly, which is one step wrong
  for the second.
- Loading the shipped sample against the merged typesystem and
  selecting the bare type returns **only subtype instances** — three
  `model.MetaData` and two `model.HuggingfaceMetaData`, matching the
  five model rows the import writes. Not one instance is the bare type
  itself, which is precisely why the bare name has to be the one
  selected.

**The rule this sets for the rest of the phase:** never move a claim out
of a legacy document. Establish it from the code, the schema or the
database, or drop it.

Step 12 is therefore only the deletion.

## 7.11 Found while writing `.env.example` — needs a decision

**Nine of the 28 settings cannot be set in `.env`.** Compose passes a
variable into a container only where `docker-compose.yml` names it, and
nine are not named:

    DUUI_DB_HOST      DUUI_TS_EMOTION              DUUI_QUERY_MAX_ROWS
    DUUI_VIDEO_DIR    DUUI_TS_IDENTITY_EMOTION     DUUI_QUERY_MAX_TOOL_ITERATIONS
    DUUI_XMI_FILE     DUUI_TS_MULTIMODAL_IDENTITY  DUUI_QUERY_STATEMENT_TIMEOUT_MS

Confirmed by running `docker compose config` with all nine set in the
environment: `DUUI_DB_HOST` and `DUUI_VIDEO_DIR` keep their fixed
values, and the other seven appear in no service's environment at all.

Two are deliberate and correct — `DUUI_DB_HOST` and `DUUI_VIDEO_DIR` are
pinned to the service name and the container path, which is what wires
the stack together. The remaining **seven look like an oversight**: the
code reads them, `.env` is the documented way to set things, and setting
them there does nothing.

**Not changed.** Adding seven `${VAR:-default}` entries to the compose
file is a behavior change, and §5 of the plan forbids incidental
behavior changes outside Phases 4 and 6. Phase 7 documents the gap
instead — marked per variable in `configuration.md`, and marked again in
`.env.example` beside each one.

**For decision** — pass the seven through, or leave them as
compose-file-only settings.
