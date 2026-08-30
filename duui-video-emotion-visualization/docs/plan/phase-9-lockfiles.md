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

## 9.3 The questions this phase cannot answer on its own

Four, and the first two decide the shape of everything else.

### Q1 — How are the Python locks produced?

| Option | What it gives | What it costs |
| --- | --- | --- |
| **`pip freeze` in the built image** | Exact versions for the whole closure, no new tool, output already clean — `pip freeze` excludes `pip`, `setuptools` and `wheel` | No hashes, so it pins *what* but not *that it is genuine*. Regenerating means rebuilding the image |
| **`pip-compile` (pip-tools)** | The same, plus `--generate-hashes`, plus a comment saying which declaration pulled each package in | A new development dependency, and a much larger file |
| **`uv pip compile`** | As above and far faster | A new tool that is not in any image today |

**Recommendation: `pip freeze`.** It needs nothing new, and the images
already exist as the thing being frozen. Hashes are worth having, but
they are a second decision about supply-chain integrity, not about
reproducibility, and mixing the two makes both harder to review.

### Q2 — Does the image install *from* the lockfile?

- **Yes** — `requirements.txt` stays the human-readable declaration,
  `requirements.lock` is what `pip install` reads, and adding a
  dependency means editing one and regenerating the other. Builds become
  reproducible. This is the standard two-file arrangement.
- **No** — the lockfile is a record of what one build produced, useful
  for diffing and for reproducing by hand, and the build keeps resolving.

**Recommendation: yes.** A lockfile the build ignores documents a
problem instead of fixing it.

### Q3 — Are base images pinned by digest?

This is the one with a real cost on both sides, and it is not a
reproducibility question with an obvious answer.

- **Pin** (`python:3.14-slim@sha256:…`) and every build is identical —
  including, permanently, whatever unpatched libraries the base held on
  the day it was pinned. Nothing tells you a rebuild would now be safer.
- **Do not pin** and rebuilds pick up security updates for free, at the
  cost of two builds a week apart differing in ways no file records.

**No recommendation.** It depends on whether this stack is ever left
running unattended, which is a question about deployment rather than
about the code, and the owner is the one who knows.

### Q4 — Are the two downloaded binaries checksum-verified?

Adding `sha256sum --check` to `Dockerfile.lint` is four lines and makes
the download verifiable rather than trusted. **Recommendation: yes** —
it is small, it is contained, and the alternative is a checker image
whose contents are decided by whoever can write to a release tag.

## 9.4 Steps

| # | Step |
| --- | --- |
| 1 | Answer §9.3 |
| 2 | Record the changelog decision in §7 of the plan overview |
| 3 | Commit `package-lock.json`; `Dockerfile.lint` uses `npm ci` |
| 4 | Generate a lockfile per Python requirements set, by the method Q1 picks |
| 5 | Point the Dockerfiles at them, if Q2 says so |
| 6 | Q3, whichever way it goes, written down with its reason |
| 7 | Q4: verify the two binaries, if agreed |
| 8 | Document how to add or upgrade a dependency now — the one thing lockfiles make non-obvious |
| 9 | Verify — see §9.5 |
| 10 | Close the phase, and the plan |

## 9.5 Verification

- **Every image rebuilt from scratch**, with no cache, and the resulting
  installed set compared against the lockfile. A lock nobody checked is
  a lock that does not hold.
- **Two builds compared.** The point of the phase is that they match;
  demonstrate it rather than assert it.
- Every checker green, full suite green, from a **fresh clone** — Phase 8
  established that as the only meaningful test of the build.
- The corpus untouched: this phase changes how software is installed,
  and should not go near the data.

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
