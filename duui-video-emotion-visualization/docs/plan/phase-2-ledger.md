# Phase 2 — Fact ledger

*Detailed plan for Phase 2. Overview, cross-cutting rules, decisions log and
progress table live in [the plan overview](README.md).*

Status: `[x]` complete, 2026-08-22.
Branch: `code-cleanup/phase-2`.

## 2.0 What this phase is for

To establish **what the system actually does**, verified against code, so that
Phases 5 and 7 have something to write from other than the existing comments —
which [§5 of the plan](README.md#5-cross-cutting-rules) forbids relying on.

Two outputs:

- **Verified facts**, per module — [`phase-2-modules.md`](phase-2-modules.md)
- **A discrepancy register** — §2.3 below, feeding Phases 3, 5, 6 and 7

Nothing is fixed in this phase. Discrepancies are recorded, not corrected. Code
*bugs*, as opposed to documentation errors, follow the stop-and-ask rule in §5.

## 2.1 Method

For each sub-project, in the Phase 5 order (smallest first): `pgvector-db` →
`global-identity-linker` → `cas-to-postgres-importer` → `webapp`.

Per module: what it owns, what it exports, what it depends on, and any behavior
that is not obvious from the signature. **Read the code; never the comments.**
Where a claim can be checked against the running database or the test suite,
check it rather than reasoning about it.

Anything that cannot be verified is recorded as unverified, with what would be
needed to settle it. It is not guessed at.

## 2.2 A correction carried over from Phase 1

Phase 1 recorded, as evidence that `pgvector-db/data_schema_with_types.md` was
stale, that `job_runs` is missing from it. **That was wrong**, and it is
corrected here and in the three places it was propagated to.

`data_schema_with_types.md` is not a description of the running database. It is
the **design document** mapping the UIMA CAS type system onto tables, and it says
so in its own header. `job_runs` is an operational table that no CAS produces, so
its absence from a pipeline-export design is correct rather than stale.

The mistake is instructive, and is exactly the failure the phase ordering exists
to catch: a plausible inference — file names two things, one is missing,
therefore stale — made without reading the document. Phase 1 should have read it.
Phase 2 did.

## 2.3 Discrepancy register

Verified findings. Every entry names where it is resolved.

### D1 — the design specifies emotion fusion that does not exist

**Closed 2026-08-22: ignore.** Verified that `FusedEmotion` /
`EmotionFusionReference` appear **only** in `data_schema_with_types.md` — not in
`schema.sql`, not in the typesystems, not in any code. Since that file is being
retired (§2.7), the fusion layer has no other trace and needs no decision.

*Original entry:* `data_schema_with_types.md` specifies
`FusedEmotion` (`fused_id`, `fusion_method`, `target_modality`, …) and
`EmotionFusionReference` (`fused_id`, `source_emotion_id`) as an n:m bridge for
combining emotions across modalities. **Neither has a table in `schema.sql`, and
nothing in the importer writes one** — `grep -i fus` over the schema returns
nothing.

The document's header carefully lists four known divergences; this is not among
them. Either the fusion layer was planned and never built, or it was dropped and
the spec was not updated. Needs a decision: implement, or record as unbuilt.

### D2 — the design document is written in mixed German and English

**Phase 7.** Headings and many column descriptions are German
("Metadaten & Video Layer", "Fortlaufender Index des Segments", `'shot'` oder
`'sentence'`), the rest English. Phase 1 settled on US English throughout.

### D3 — `data_schema_with_types.md`'s stated divergences are accurate

**No action.** Recorded because it is evidence, not a problem. Checked against
`schema.sql`: `begin`/`end` → `begin_offset`/`end_offset` (reserved word);
`Detection` split into `face_detections` and `person_detections`; `segments` also
fed by `SpeakerSentence` for `kind = 'sentence'`; text emotion from a second UIMA
type. All four hold.

Its composite-key note is *directionally* right and wrong in detail — the keys
really are `(video_id, <id>)`, but the ids do not "restart at 1" per document.
See D7.

### D4 — no `connect_timeout` in any application code

**Closed 2026-08-29** by
[fix-d4-connect-timeout.md](fix-d4-connect-timeout.md), on its own branch
between Phase 5 and Phase 6.

Carried from [Phase 0 §0.2](phase-0-baseline.md). Against a host that accepts
the route but never answers, `psycopg2.connect()` waited on the operating
system's TCP timeout — reproduced as still hanging at 25 seconds with nothing
printed.

**This entry understated the scope.** It named three call sites; there were
five. The two it missed are the job runs' own connections, in both copies of
`job_runs.py`, where a hang produces neither progress nor an error.

`connect_timeout` now lives in `DB_CONFIG` in all three settings modules, so
every connection inherits it, read from `DUUI_DB_CONNECT_TIMEOUT` with a
default of 10. Verified: each service now fails cleanly instead of hanging, and
the webapp **starts** against an unreachable database, logs a diagnostic naming
the host, and answers `/healthz` with 503 in ten seconds rather than never
listening at all.

### D5 — the importer announces work it then skips

**Phase 5.** Carried from Phase 0 §0.5. `pipeline.py:207` prints
`Loading CAS data from <file>...` before the already-imported check at `:227`;
the actual load is at `:253`.

### D6 — emotion labels are model-native and differ by modality

**No action; already in the glossary.** Carried from Phase 1. Video uses eight
capitalized labels, text lowercase GoEmotions-style ones, audio its own set, plus
`<unk>` and empty `dominant_label` values.

### D7 — a rationale comment's illustration is contradicted by the data

**Phase 5.** `linking.py`'s header explains the composite `(video_id, person_id)`
key by asserting that "two videos routinely both have a 'person 1'."

**The mechanism is real; only the word "routinely" overstates it** (confirmed by
the project owner, 2026-08-22 — ids genuinely can collide across videos; this
corpus is simply too small for it to show).

`person_id` is the CAS's `xmi:id`, a *document-wide* counter across all
annotations. In this corpus the values are large and sparse — `32608`, `70438`,
`87720`, `132525`, `1755` — and no `person_id` occurs in more than one video.
The ranges differ wildly per file, which is the real evidence that they are
document-scoped and cannot be assumed unique corpus-wide.

So the composite key is right and the reason is right. Phase 5 should keep the
reason and state it in the form that can be checked — per-document counters,
ranges differing per file, collisions therefore possible — rather than asserting
a collision the data does not show.

**Settled 2026-08-22, during Phase 3 — with proof.** Collisions are not merely
possible, they are abundant: **4,762 `emotion_id` values occur in more than one
video** in this corpus. `emotion_id` 16621 is in videos 3 and 6.

The `persons` table is simply too small a sample to show it — 23 rows. The
mechanism is identical, since both columns are the CAS's `xmi:id`.

Two corrections to this entry follow:

- The composite key's justification is fully verifiable, and the numbers above
  are what Phase 5 should cite.
- **There is no coverage gap.** `cas-to-postgres-importer/tests/test_identity.py`
  already has `test_two_videos_can_hold_the_same_xmi_id`, whose comment names
  16621 and the two videos. That comment is accurate — checked against the
  database. Nothing for Phase 6 to add.

### D8 — `--on-existing replace` does not preserve `video_id`

**Phase 5 (document), Phase 7 (operations).** Verified by observation during
Phase 0: `first2.mp4` was `video_id 1` before an `--on-existing replace` run and
is `video_id 47` after it. Replace deletes the row and inserts a new one, so the
`BIGSERIAL` advances.

Consequences worth documenting: any external reference to a `video_id` — a
bookmarked webapp URL, a saved query, an exported result — breaks after a
replace. The gap from 10 to 47 also shows the sequence has been consumed by
earlier rolled-back imports, so ids are neither stable nor contiguous.

Not a bug: delete-and-insert behaving as delete-and-insert. But it is undocumented
and it is the kind of thing a user discovers the hard way.

### D9 — `/api/stats` is served and tested but has no consumer

**Open, deliberately.** Decided 2026-08-22: **keep the code as it is**, and keep
this entry registered rather than closing it. Not a defect — the endpoint works
correctly; it simply has no caller. Registered so it stays visible and does not
get rediscovered as a surprise later. `routes/stats.py`,
`queries/stats.py` (120 lines, four functions) and the `/api/stats/{video_id}`
endpoint are live and return 200. **Nothing calls them.** `grep` over the whole
frontend finds one hit, and it is the comment in `api.js` saying so.

The comment is accurate — one of the few that checks out: the emotion panels
replaced the insights panel that used to read it. `test_routes.py` asserts the
route exists, and `test_emotion_series.py` / `test_video_scoping.py` exercise the
query functions, so it is tested code with no product behind it.

Decision needed: remove the route and its queries, or keep them as a documented
API for external use. Not a bug either way.

### D10 — `accessibility.md` uses retired terminology

**Phase 5/7, small.** `webapp/docs/accessibility.md` is factually correct — the
one pre-existing document that is — but it says "viewer" twice, which Phase 1
retired in favor of "webapp", and its heading and prose style predate the style
guide. Content keeps; terminology and style get a pass.

### D11 — `a11y-baseline/` is sound, contrary to first impressions

**No action.** Checked because it was suspected of being stale. It is a
**deliberately historical snapshot** — "Captured 2026-08-20, before any
remediation work" — so describing a state that no longer exists is its purpose,
not a defect. Its reproduction instructions were checked too: `../../../` from
`webapp/docs/a11y-baseline/` really does resolve to the project root. Accurate
as written.

### D12 — 17 code references point at documentation that has moved or been replaced

**Phase 5, across 15 files.** Quarantining the root `README.md` and the design
document (§2.7) invalidated every in-code pointer to them. Verified count: **17
references in 15 files**, split three ways.

1. **Now broken by the move** — `pgvector-db/schema.sql:134` and
   `cas-to-postgres-importer/src/main/config.py:138` cite
   `data_schema_with_types.md`, now `docs/legacy/data-schema-design.md` and due
   for deletion. Their targets become `docs/database.md`.
2. **Already broken before the move** —
   `webapp/src/backend/query_agent/schema_context.py:11` cites
   `docs/data_schema_with_types.md`. That path never existed; the file was in
   `pgvector-db/`. A pre-existing error, found by this check.
3. **"See README" pointers** — the three `Dockerfile`s, `docker-compose.yml`, the
   three `conftest.py` files, `app.py`, `db.py`, `queries/stats.py`, `media.py`
   and `pipeline.py` refer to README sections ("Docker architecture", "Tests",
   "Configuration reference") that no longer exist at the root. Each must be
   repointed at whichever `docs/` page now owns that subject, per the map.

Left broken deliberately: Phase 2 changes no source, and Phase 5 rewrites all of
these comments anyway. Recorded at this precision so none is missed.

### D13 — the test database vanished without explanation

**Phase 6.** `duui_baseline_test` — the empty schema-applied database the suite's
green baseline depends on — was created during Phase 3 step 10 and confirmed
working (150/150). It was **gone by Phase 4**, while `duui_video_emotion` in the
same volume kept all 375,205 rows. The volume was never recreated; the
`pgvector-db` container was, after an image rebuild.

**Cause established 2026-08-22:** the project owner rebuilt the stack, because
the containers had become orphaned from their images. A rebuild recreates the
volume, and `duui_baseline_test` does not survive one — it is created by hand,
not by `schema.sql`, so nothing recreates it. The corpus looked untouched only
because Phase 3 proved the import is deterministic: the same nine files produce
the same 375,205 rows every time.

Recreating the database restored 150/150 immediately.

Whatever the cause, it makes the point Phase 6 already decided: the green
baseline currently depends on a hand-created database that nothing recreates,
nothing documents, and nothing notices the loss of — the run just quietly
reports 121 passed, 29 skipped. Testcontainers removes the whole class of
problem.

### D14 — a NameError I introduced in Phase 3, found by the linter in Phase 4

**Fixed 2026-08-22.** `pipeline.py:89` reads `xmi_file = xmi_file or XMI_FILE`,
but the Phase 3 split of `pipeline.py` into `inputs.py` removed `XMI_FILE` from
the `from .config import …` line, because the new module needed it. Calling
`run()` with no argument therefore raised:

```text
NameError: name 'XMI_FILE' is not defined
```

**Why nothing caught it for a whole phase.** `run()` is only ever reached
through `run_many()`, which always passes an explicit path. The `or XMI_FILE`
fallback exists for the documented single-file workflow — `DUUI_XMI_FILE` — and
nothing in the suite exercises it. A green 150/150, a working importer, a full
corpus rebuild and an end-to-end browser check all passed over it.

Found by `ruff`'s F821 the first time the linter was pointed at the repository,
before it had been run even once in anger. Fixed by restoring the import; `run()`
now raises the `ValueError` it was always supposed to.

Two things worth keeping from this:

- **Static analysis found in seconds what four phases of testing missed.** It is
  the strongest available argument for step 9's CI job.
- **The gap is a test gap too.** Nothing covers `run()`'s no-argument path,
  which is a documented entry point. Phase 6 should decide whether to cover it
  or to remove the fallback.

### D15 — three user-facing surfaces give three different project names

**Needs a decision; not a defect.** Found during Phase 4's final verification.

| Surface | Says |
| --- | --- |
| `index.html` `<title>` — the browser tab | `DUUI Emotion Visualization` |
| `index.html` `<h1 class="topbar-title">` | `Emotion Visualization` |
| `app.py` `FastAPI(title=…)` — the OpenAPI document | `DUUI Video Emotion Visualization` |

**Why Phase 3 missed two of them.** That phase swept for `bundestag`, and only
the FastAPI title contained it (`DUUI Bundestag Video Viewer`). The other two
never held the dead name, so nothing brought them into the sweep — a search for
the *wrong* name cannot find a name that is merely inconsistent.

Nothing is broken; three surfaces simply disagree. The glossary settles what the
project is called, so the `<title>` and the OpenAPI title should match it. The
`<h1>` is a visible design element and dropping "DUUI" there may well be
deliberate, so it is not obviously the same question.

Left for a decision rather than changed here: these are strings a person sees,
and Phase 4 is a tooling phase.

<!-- New entries append here as each sub-project is read. -->

## 2.4 Shared contracts

Verified from both sides. These are what `docs/architecture.md` will own, and
what no sub-project README may restate.

### The database

The only integration point between the four parts. There is no API between
sub-projects, no message queue, and no shared code — everything one part tells
another, it says by writing a row.

| Writer | Reader | Through |
| --- | --- | --- |
| importer | webapp | every CAS-derived table |
| importer | linker | `face_embeddings`, `voice_embeddings`, `persons` |
| linker | webapp | `global_persons`, `persons.global_person_id`, `persons.global_person_match_score` |
| importer, linker | webapp | `job_runs` |

`persons.global_person_id` is written **only** by the linker — verified: no
typesystem defines `GlobalPerson` and no parser step touches the column.

### The video store

One directory, `DUUI_VIDEO_DIR`. The importer copies each CAS's video in under
the exact name it writes to `videos.filename`; the webapp mounts the same
directory read-only at `/media` and resolves a video as
`<video store>/<videos.filename>`. **Filename is the join key, not `video_id`** —
which is what makes D8 survivable.

### Environment variables

Every sub-project defines its own config module reading the same `DUUI_*`
names. No config code is shared. Compose passes identical values to every
service, which is what keeps both ends of the database and video-store contracts
pointing at the same place.

The two the contracts depend on are `DUUI_DB_*` and `DUUI_VIDEO_DIR`.

### `job_runs`

The channel from the two batch jobs to the webapp. Declared identically in four
places. A writer opens its **own autocommit connection**, separate from the
transaction doing the work, so progress stays visible while a long import or
recompute sits uncommitted. The webapp polls `GET /api/jobs` and treats a run
whose heartbeat is older than `STALE_AFTER_SECONDS = 30` as dead.

## 2.5 Progress

| Sub-project | Modules | Read |
| --- | --- | --- |
| `pgvector-db` | 2 files | `[x]` both verified |
| `global-identity-linker` | 5 modules | `[x]` all read, claims checked |
| `cas-to-postgres-importer` | 15 modules | `[~]` structure and contracts verified; `config.py`, `media.py` and the 11 parsers not yet read line by line |
| `webapp` | 14 backend, 15 JS, 12 CSS | `[~]` backend structure and the live API surface verified; `query_agent/`, the JS modules and the CSS not yet read line by line |

**What "read" means here.** Every module has been placed: what it owns, what it
exports, what depends on it, and the contracts it participates in. Specific
checkable claims were checked against the database, the typesystems, or the
running app. What remains is line-by-line reading of the four largest areas,
which is where Phase 5 will spend its time anyway — the question is whether that
reading happens now or as part of rewriting each file.

## 2.6 Exit criteria

- [x] Every module placed and recorded in [`phase-2-modules.md`](phase-2-modules.md)
- [x] Shared contracts written up (§2.4)
- [x] Design document verified against `schema.sql` — D1–D3
- [x] Discrepancy register: **D1–D12**, every entry assigned to a phase
- [x] Line-by-line reading — **deferred to Phase 5 by decision.** It is the same
      reading Phase 5 must do to rewrite each file; doing it twice buys nothing.
- [x] README claims verified — **moot.** The README was quarantined instead of
      checked (§2.7), so there is nothing left to verify.

**Phase 2 is complete.**

## 2.7 The legacy quarantine

The root `README.md` and `pgvector-db/data_schema_with_types.md` were moved to
`docs/legacy/` rather than verified or rewritten. **Phase 7 deleted that
directory** (2026-08-30), so the text below describes a quarantine that no
longer exists; the files are in git history.

Verifying them now would have been work thrown away: much of what they claim
describes commands, paths and service names that Phases 3 and 4 will change.
Rewriting them now is Phase 7's job, and Phase 7 has to write against a finished
state that does not exist yet. Leaving them in place was the worse option — the
root README is the first file anyone opens and it reads as authoritative.

They are kept, not deleted, because their *claims* are unreliable while their
*topics* are real: quickstart, configuration, operations, cross-video identity,
job status. Phase 7 uses that list so no section is forgotten, then deletes both.

A short replacement `README.md` now sits at the root. Every claim in it was
checked against the running system before it was written.

## 2.8 What this hands to later phases

| To | What |
| --- | --- |
| Phase 3 | D9 (`/api/stats` has no consumer — keep, but registered). The `job_runs` DDL exists in four identical copies. `queries/stats.py` is 120 lines with no product behind it. |
| Phase 5 | D4 (no `connect_timeout`), D5 (importer's misleading skip message), D7 (state the composite-key reason in checkable form), D8 (document `video_id` instability), D10 (terminology in `accessibility.md`), **D12 (17 stale doc references across 15 files)**. Plus the line-by-line reading deferred here. |
| Phase 6 | D7's coverage gap — nothing tests two videos sharing a `person_id`, which is the case the composite key exists for. D9's tests. |
| Phase 7 | §2.4's shared contracts → `docs/architecture.md`. The design document's tables → `docs/database.md`. Both legacy files deleted at the end. |
