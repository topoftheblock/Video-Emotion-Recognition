# Architecture

How the four sub-projects fit together, and the contracts they share.

Values for every setting named here are in
[configuration.md](configuration.md); the schema itself is in
[database.md](database.md).

## The four parts

Work arrives as CAS files produced by a DUUI pipeline, outside this
project. Everything here begins with those files.

**[`pgvector-db`](../pgvector-db/)** is Postgres with the pgvector
extension, and `schema.sql` baked into the image. It holds every table
the other three use. It runs the schema only when its data directory is
empty, which makes a first start and a restart behave differently — see
[operations.md](operations.md).

**[`cas-to-postgres-importer`](../cas-to-postgres-importer/)** reads a
CAS file, writes its annotations into the database, and copies the video
the CAS names into the video store. It is a job: it runs, does the work
and exits. One transaction per file, so a malformed file costs that file
and not the batch.

**[`global-identity-linker`](../global-identity-linker/)** decides which
people in different videos are the same person, by comparing the face
and voice embeddings the importer has already loaded. It clears every
global person and rebuilds them from scratch on each run, so its result
depends on what is in the database and not on the order videos arrived
in. It is also a job.

**[`webapp`](../webapp/)** serves the interface: a FastAPI backend and a
static frontend. It reads the database and the video store. The one
thing it writes is described under *Job status reporting* below.

The flow is one-directional. The importer writes; the linker reads what
the importer wrote and writes its own conclusions; the webapp reads
both. Nothing reads back into the pipeline.

## Shared contracts

Everything below is depended on by more than one sub-project. This page
is the only place any of it is explained; the sub-project READMEs link
here.

### The database

The integration point. The three sub-projects never call each other —
there is no HTTP between them, no queue, and no shared library. What one
writes, another reads, and the schema is the whole of the agreement.

That is why `pgvector-db` owns `schema.sql` rather than any of the
three: a table belongs to the contract, not to whichever service
happens to write it first.

### The video store

One directory, named by `DUUI_VIDEO_DIR`, holding the video files the
webapp plays.

The contract is a filename. A video's row carries `videos.filename`, and
its file is at `<video store>/<that filename>`. The importer puts it
there — copying the file that arrived beside the CAS, or extracting it
from the CAS itself when no such file exists — and the webapp reads it.
Nothing else is agreed: not a directory layout, not an id in the name.

The webapp mounts the store read-only, and checks for each video whether
its file is actually present rather than assuming the row implies it.

### Environment variables

Each sub-project defines its own settings module, reading the same
`DUUI_*` variables. The modules are separate files with no import
between them; the variable *names* are the contract.

This is what lets a value be set once, in one `.env`, and reach three
containers that share no code. Where two sub-projects must agree on
something — the database, the video store — they agree by reading the
same variable, not by importing the same module.

### Job status reporting

The two jobs run for as long as their work takes, and the webapp has to
be able to say that something is happening. The channel is the
`job_runs` table: a job writes a row when it starts, updates it as it
goes, and closes it when it finishes.

A row also carries a heartbeat. A job that is killed never writes its
final row, so a row can claim to be running long after its process is
gone; the age of the heartbeat is what distinguishes working from dead.
The next run of the same job closes out any stale row it finds.

This is the one thing the webapp writes. It creates `job_runs` at
startup if the table is missing, because the schema runs only on an
empty data directory and the webapp is the service that is always up.
That write is best-effort: if it fails, the webapp still starts.

## Why the sub-projects share no code

They are separate images, built from separate directories, and no file
is shared between them. That is a deliberate constraint, and it has a
price paid in three places:

| File | Copies |
| --- | --- |
| `db.py` | 3 |
| `config.py` | 3 |
| `job_runs.py` | 2 |

The two copies of `job_runs.py` are byte-identical apart from the prefix
each writes on its log lines. They are kept that way on purpose: the
table they write is part of the shared contract, so the two writers must
not drift. The same holds for the DDL that creates that table, which
exists in four places — `schema.sql` and three modules — and is
identical in all of them.

What the constraint buys is that each part can be built, run and
reasoned about on its own. A change to the importer cannot break the
webapp except through the database, which is exactly the surface this
page describes.
