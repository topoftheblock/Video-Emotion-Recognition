# Architecture

How the four sub-projects fit together, and the contracts they share.

> **Stub.** Structure only — headings are the agreed shape, prose is written in
> Phase 5 (as rationale moves out of code) and Phase 7 (connective text).
> Nothing here may be written from existing comments; see
> [documentation-style.md](documentation-style.md) §2.

## The four parts

<!-- What each is, in one paragraph, and the direction data flows between them. -->

## Shared contracts

Everything below is depended on by more than one sub-project. This page is the
only place any of it is explained; sub-project READMEs link here.

### The database

<!-- Why a shared Postgres is the integration point.
     Schema detail -> database.md -->

### The video store

<!-- The DUUI_VIDEO_DIR contract: importer writes, webapp reads,
     <video store>/<videos.filename>. -->

### Environment variables

<!-- Why each sub-project defines its own config module from the same DUUI_*
     variables rather than sharing code. Values -> configuration.md -->

### Job status reporting

<!-- The job_runs table as the channel between the two batch jobs and the
     webapp. Heartbeats and staleness. -->

## Why the sub-projects share no code

<!-- The standalone rule and what it costs: duplicated job_runs.py, db.py,
     config.py. Rationale moved out of the code lands here. -->
