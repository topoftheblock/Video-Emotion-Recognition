# Phase 9 — Lockfiles

Branch: `code-cleanup/phase-9`. The last phase. After it,
`code-cleanup/main` merges into `main` once, and that merge is also what
finally exercises the CI workflow Phase 8 could not observe.

**Changelogs are dropped** (decided 2026-08-30, by the project owner).
§7 item 10 of the plan overview had scheduled one per sub-project plus a
root `CHANGELOG.md` as the final step; they are not wanted. Git history
carries the same information, and this pass has kept it legible on
purpose — one commit per logical step, every message prefixed with its
phase. The decision is recorded in §7 rather than silently dropped.

So this phase is about one thing: **two builds of this project a month
apart should install the same software.** Today they may not.

---

## 9.1 What is binding

[§5 of the plan overview](README.md) applies unchanged. Three parts of it
bear directly on this phase:

- **Sub-projects share no files.** So there is no shared lockfile. Each
  gets its own, beside the `requirements.txt` it locks.
- **A found bug stops the work.** Locking exposes what is installed; if
  something unexpected is in there, that is a finding, not a footnote.
- **Decisions get written down, including the ones that end in "no
  change".** This phase is mostly decisions.

**One constraint needs stating explicitly.** §1 fixes the inner layout of
a sub-project: `src/`, `tests/`, `.dockerignore`, `Dockerfile`,
`pyproject.toml`, `requirements.txt`. A lockfile adds a file to that
list. That is sanctioned — the plan has scheduled lockfiles for Phase 9
since it was written — but it is the one place this phase touches a fixed
constraint, so it is named here rather than assumed.

## 9.2 The starting state, measured 2026-08-30

Nothing in this project is locked. Not the Python dependencies, not the
Node tooling, not the base images, not the action it runs in CI.

### Python: 13 declared packages, 39 installed

Every requirement is floor-and-ceiling pinned (`>=x,<y`), which stops a
new major arriving silently and does nothing about anything else.

| | Declared | Installed |
| --- | --- | --- |
| `cas-to-postgres-importer` | 4 | 11 |
| `global-identity-linker` | 2 | 2 |
| `webapp` | 7 | 26 |
| `requirements-dev.txt` | 2 | — |
| The `tests` image, which installs all four | 15 | 42 |

**The gap is the transitive closure.** The webapp declares 7 packages and
gets 26; nineteen of them are chosen by the resolver at build time and
named nowhere. A rebuild next month picks whatever satisfies the ranges
then.

`global-identity-linker` is the exception and worth noting: 2 declared,
2 installed, no transitive dependencies at all. Locking it is nearly a
formality — which is a point in favour of doing all three the same way
rather than only where it looks worthwhile.

### Node: 8 declared, 216 installed, no lockfile at all

`package.json` declares eight development tools with `^` ranges.
`Dockerfile.lint` runs `npm install`, which resolves them fresh on every
build, into **216 packages**.

**This is the largest hole and the cheapest to close.** `npm` produces
`package-lock.json` by default; the project simply never committed one,
and the Dockerfile uses `npm install` rather than `npm ci`. Nothing here
ships to a user — it is the checker image — but it is the image that
decides whether the build passes, so a silent change in it is a silent
change in what "green" means.

### Base images: four floating tags

    python:3.14-slim         ×4  (three services and both runner images)
    pgvector/pgvector:pg18   ×1
    node:24-trixie-slim      ×1  (COPY --from in Dockerfile.lint)

All are moving tags. `python:3.14-slim` is rebuilt whenever its Debian
base takes a security update, which is usually what you want and is
exactly what a lockfile is not.

### Two binaries fetched over the network

`Dockerfile.lint` pins hadolint 2.12.0 and actionlint 1.7.7 by version
and downloads both from GitHub releases with `ADD`. The version is
pinned; **what arrives is not verified**. A release asset can be
replaced under a tag.

### CI: one action, on a floating major

`actions/checkout@v4`, used twice. `v4` is a moving tag by design.

## 9.3 The questions, answered

Answered 2026-08-31 by the project owner. The phase came out much
smaller than its own measurements suggested, and most of what is left is
writing down why.

### Python dependencies stay as they are

**No Python lockfiles.** The floor-and-ceiling ranges stay, and the
images keep resolving at build time. So the 39-installed-from-13-declared
gap in §9.2 is accepted rather than closed, and two builds a month apart
may still differ in the transitive set.

This is the decision, not an oversight, and it is worth being plain
about what it costs: nothing records which nineteen packages the webapp
image actually got. If a rebuild ever behaves differently, the way to
find out why is `pip freeze` in both images and a diff — there is no
file to consult.

### The images do not install from any lockfile

Which follows from the above for Python, and is stated separately
because it also settles the shape of anything added later: a lockfile in
this project is a **record**, not a build input. Nothing in a Dockerfile
reads one.

### Base images are recorded, not pinned

The chosen answer to the trade-off §9.2 raised, and the more
conservative side of it.

`FROM python:3.14-slim` and the other two stay as floating tags, so a
rebuild keeps picking up security updates to the base — which is the
thing digest pinning would have frozen, permanently and silently.
Instead the digests are written to a tracked file that **nothing
consumes**: a record you can diff, and reproduce from by hand if a
rebuild ever misbehaves.

The honest limit of this: it records what a build used, and does not
make the next build match it.

### The two downloaded binaries are not checksum-verified

`Dockerfile.lint` keeps `ADD` on the hadolint and actionlint release
assets, pinned by version and unverified in content.

### The Node tooling is left alone

**Out of scope by decision**, including the `package-lock.json` that
does not exist. The lint image's 8 declared tools keep resolving to 216
packages fresh on every build.

The cost, recorded because §9.2 measured it: this is the image that
decides whether a build is green, so a change inside it changes what
green means, and nothing records that it changed. If the checkers ever
start failing or passing for no reason anyone can see, this is the first
place to look.

## 9.4 Steps

Small, after §9.3. Four of the six things measured are deliberately not
being changed, so most of this phase is the record of that.

| # | Step |
| --- | --- |
| 1 | Answer §9.3 — done |
| 2 | Record the changelog decision in §7 of the plan overview — done |
| 3 | `tests/refresh-image-digests.sh`, and the `docker-images.lock` it writes — done |
| 4 | Document what that file is, what it is not, and how to refresh it — done, in `operations.md` |
| 5 | Write the four "no change" decisions into the plan's §7, where they can be found without reading this file — done |
| 6 | Verify — see §9.5 — done |
| 7 | Close the phase, and the plan — done |

## 9.5 Verification

Smaller than it was, because less is changing.

- **The script runs**, and the digests it writes match what
  `docker image inspect` reports for the images the build actually used.
- **Nothing consumes the file.** Demonstrated rather than asserted: grep
  the Dockerfiles, the compose file and the runners for its name, and
  build an image with it deleted.
- **The refresh is idempotent** — running it twice against unchanged
  images produces no diff.
- Every checker green and the full suite green, from a **fresh clone**.
- The corpus untouched. This phase does not go near the data.

## 9.6 What closing this phase means

Phase 9 is the end of the cleanup. When it merges:

- `code-cleanup/main` merges into `main`, once, as §5 has said
  throughout.
- That merge is a push to `main`, which is what finally triggers the
  workflow — closing the one exit criterion Phase 8 could not reach, and
  the reason a pull request is the right way to do it.
- **Two decisions remain open in [`todo.md`](../todo.md)** and neither is
  in scope here: whether `schema.sql` should be idempotent throughout,
  and whether to retire `DUUI_XMI_FILE`. They are deliberately not
  blockers.

---

## 9.7 Verification — the record

Done 2026-08-31.

- **The script runs and is idempotent.** Two consecutive runs against
  unchanged images produce no diff, checked before and after an edit to
  the script's own comments.
- **The digests are the right ones.** `docker image inspect` on
  `python:3.14-slim` reports
  `sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4`,
  which is what the file records.
- **Nothing consumes the file**, demonstrated twice rather than
  asserted: a grep across the Dockerfiles, the compose file, the runners
  and the Python sources finds no reference outside the script that
  writes it; and the webapp image builds with the file deleted.
- **From a fresh clone**, not from this working tree: every checker
  green, 221 tests pass, the record ships with the clone, and the
  refresh script run there produces no diff — so the file describes the
  images rather than this machine.
- The corpus was not touched. This phase went nowhere near the database.
