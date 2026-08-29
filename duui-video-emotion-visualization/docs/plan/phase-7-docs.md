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

## 7.2 The starting state, measured

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

25 `DUUI_*` names are read by application code. Six more appear only in
`docker-compose.yml` or `.env.example` and are read by nothing in `src`:

    DUUI_DB_HOST_PORT     DUUI_TEST_DB_NAME    DUUI_TEST_UID
    DUUI_VIDEO_STORE      DUUI_WEBAPP_HOST_PORT DUUI_TEST_GID

Those are Compose-level knobs — ports, volume names, the uid the test
container runs as. `configuration.md` owns every one of them, and must
say which layer reads each, because "grep the source" will not find six
of them.

## 7.3 The `a11y-ci.yml` item, re-checked

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

The repository root does hold 13 sibling projects, so the *caution* is
reasonable even though the stated facts are not. Rewrite the header to
give the real reason — a deliberate choice not to spend CI minutes on a
browser download — and say what activating it would involve. **Do not
activate it.**

## 7.4 What Phase 5 and Phase 6 left owing

- `webapp/docs/a11y-verification.md` is titled "after Phases 1–5",
  meaning the accessibility remediation phases. Beside a cleanup effort
  with its own Phase 5, that is confusing. Retitle by what it records,
  not by when.
- `docs/todo.md` has one entry and an empty "Open" section. Decide
  whether it earns its place or folds into the plan.
- The two gaps Phase 6 left open — `query_agent/agent.py` coverage and
  the `routes/videos.py` payload path — belong in `todo.md` if it
  survives.

## 7.5 Steps

| # | Step |
| --- | --- |
| 1 | Answer §7.7 |
| 2 | `docs/architecture.md` — the four parts, the four shared contracts, and why no code is shared |
| 3 | `docs/configuration.md` — all 31 variables, each verified against the code or the compose file that reads it |
| 4 | `docs/operations.md` — everyday commands, importing, recomputing, schema upgrades on an existing volume, the Compose-rename hazard, backup, CI |
| 5 | Finish `docs/database.md`'s two placeholders |
| 6 | The four sub-project READMEs, to the map's five-question shape |
| 7 | `tests/README.md` — what the directory is, since it holds no tests |
| 8 | Root README — drop the banner, add the links, adopt the short `run` form, note where CI lives |
| 9 | `.env.example` — one-line gloss per variable, pointing at `configuration.md`; kill the duplication |
| 10 | Rewrite the `a11y-ci.yml` header (§7.3); retitle `a11y-verification.md` |
| 11 | Font attribution: Oxanium, Roboto and Ubuntu Mono are third-party, OFL/UFL, licences alongside |
| 12 | Rewrite the three references into `docs/legacy/` (§7.8), then delete it |
| 13 | Verify — see §7.6 |

## 7.6 Verification

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

## 7.7 Questions, answered

1. **`docs/legacy/` is deleted** (2026-08-29). Its content is not used
   and is known to be unreliable; leaving it is a trap for the next
   reader. See §7.8 for what that costs.
2. **`docs/todo.md` stays**, and the work Phase 6 left open moves into
   it — so "what is left" has one address that is not the plan.
3. **`pgvector-db/README.md` is short**: what the image is, the pgvector
   version, that the schema runs only on an empty volume, and a link to
   `database.md`.
4. **The root README keeps a minimal configuration section**: the two
   input-path variables a first run with real data must set, and a link
   to `configuration.md` for the rest.

## 7.8 Deleting `docs/legacy/` orphans three live references

Found before agreeing to the deletion, not after. Outside the plan
folder — where references to it are historical record and stay — three
files point into `docs/legacy/`:

| File | What it says |
| --- | --- |
| `cas-to-postgres-importer/src/importer/cas/types.py` | "The design mapping (`docs/legacy/data-schema-design.md`) specifies the bare `annotation.MetaData` type here" |
| `webapp/src/backend/query_agent/schema_context.py` | Names it as one of three sources the schema semantics were cross-checked against |
| `docs/database.md` | An opening paragraph distinguishing itself from it |

Two of those cite the document as **evidence for a decision**. That is
the awkward part: the deletion is justified precisely because the
document is unreliable, so migrating its claims into a surviving page
would carry the unreliability forward.

**The rule for this phase:** do not move a claim out of a legacy
document. Restate what the *code* shows and drop the citation. For
`types.py` that means saying what the importer selects and why —
selecting the bare type picks up its subtypes, which is checkable. For
`schema_context.py` it means listing the sources that still exist. The
paragraph in `database.md` exists only to contrast with the legacy file
and goes with it.

Step 12 therefore reads: rewrite those three, then delete.
