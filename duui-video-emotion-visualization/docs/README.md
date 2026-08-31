# Documentation

Index and map for this project's documentation. It defines **who owns what**, so
that every question has exactly one document that answers it and the rest link.

## Index

| Document | Read it for |
| --- | --- |
| [`../README.md`](../README.md) | What this project is, and how to run it the first time |
| [`architecture.md`](architecture.md) | How the four sub-projects fit together, and the contracts they share |
| [`configuration.md`](configuration.md) | Every environment variable |
| [`database.md`](database.md) | The schema, table by table |
| [`operations.md`](operations.md) | Running and maintaining the stack after the first run |
| [`glossary.md`](glossary.md) | The one correct name for each concept |
| [`documentation-style.md`](documentation-style.md) | How to write anything in this repository |
| [`todo.md`](todo.md) | Work that is wanted but not yet scheduled |

Each sub-project has its own `README.md` and may have its own `docs/`:
[`webapp`](../webapp/README.md),
[`cas-to-postgres-importer`](../cas-to-postgres-importer/README.md),
[`global-identity-linker`](../global-identity-linker/README.md),
[`pgvector-db`](../pgvector-db/README.md). The project root's
[`tests/`](../tests/README.md) holds the runners and the checkers rather than
any tests.

## The map

Ownership is stated as much by what a document **must not** contain as by what it
does. The second column is the load-bearing one: it is what stops the same
explanation from appearing in five places and drifting five ways.

### Root

| Document | Audience | Owns | Must not contain |
| --- | --- | --- | --- |
| `README.md` | **A user, first.** Then anyone orienting. | What this is, the four parts and how they fit, prerequisites, one quickstart path, links onward. A two-minute read. | Configuration detail, architecture depth, operational procedure, anything a sub-project owns |
| `docs/architecture.md` | Developers | How the four parts fit; the shared contracts — database, video store, environment variables, `job_runs` | Per-part internals; schema detail |
| `docs/configuration.md` | Users, operators | **Every** environment variable, in one place | Anything that is not a setting |
| `docs/database.md` | Developers | The schema, written from `schema.sql` | Application logic |
| `docs/operations.md` | Operators | Running, upgrading, backup, schema changes on an existing volume, CI | First-run instructions |
| `docs/glossary.md` | Everyone | One name per concept | Explanations of how things work |
| `docs/documentation-style.md` | Contributors | How to write | Project facts |
| `docs/todo.md` | Whoever picks the work up | Wanted work, and why it is not done | Anything already done, or in progress |

### Per sub-project

Each of the four gets a `README.md` answering, in this order:

1. What it is
2. How to run it on its own
3. How to configure it
4. How to test it
5. Where the detail is

Self-contained enough to work on that part alone — but see rule 3 below.

`<sub-project>/docs/` holds detail belonging to exactly one part.
[`webapp/docs/accessibility.md`](../webapp/docs/accessibility.md) is the model.

## The rules that follow

1. **Configuration lives in `docs/configuration.md`.** `.env.example` carries a
   one-line gloss per variable and links there. The root README lists only the
   variables a first run needs.
2. **The schema lives in `docs/database.md`**, written from `schema.sql` and
   verified against it.
3. **A sub-project README never explains a shared contract.** It links to
   `docs/architecture.md`. "Self-contained" means you can work on that part
   without reading the other three, not that every document restates the
   database contract.
4. **The root README never explains a sub-project.** It links.
5. **Terminology comes from [`glossary.md`](glossary.md)**, everywhere, including
   code identifiers and user-facing output.

## Writing anything here

Read [`documentation-style.md`](documentation-style.md) first. The two rules that
matter most in this repository:

- **Write only what you can verify** against code, schema, database, or tests.
- **Documents and comments predating this pass are not evidence.** They are
  legacy text and may be outdated or wrong, including about intent. If something
  matters and cannot be verified, ask — do not infer it.
