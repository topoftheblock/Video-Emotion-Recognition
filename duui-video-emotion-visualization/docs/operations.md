# Operations

Running and maintaining the stack after the first run. First-run
instructions are in the [root README](../README.md); every setting named
here is described in [configuration.md](configuration.md).

## Everyday commands

```bash
docker compose up -d          # database and webapp
docker compose ps             # what is running
docker compose logs -f webapp # follow one service
docker compose down           # stop, keeping the data
```

`down` keeps the volumes. `down -v` deletes them, and with them every
imported row and every video in the store.

## Importing new material

```bash
docker compose run --rm cas-to-postgres-importer
```

That imports everything in the input directory. Naming paths imports
those instead — any mix of files and directories:

```bash
docker compose run --rm cas-to-postgres-importer /data/input/xmi/one.xmi
```

Those are paths *inside the container*. What is mounted onto them is set
by `DUUI_INPUT_XMI_DIR` and `DUUI_INPUT_VIDEO_DIR`.

The importer is held behind a Compose profile so it never runs as a side
effect of `docker compose up`: it writes to the database, and that
should be something you ask for. Naming the service directly activates
its profile, so no `--profile` flag is needed. On older Compose versions
that did not do this, add `--profile import`.

### Importing the same file twice

By default a CAS whose video is already imported is skipped, without
even being loaded — which is what makes re-running over a growing input
directory cheap.

```bash
docker compose run --rm cas-to-postgres-importer --on-existing replace
```

`replace` deletes the existing video and everything hanging off it, then
imports fresh, so the rows match the file being imported rather than
merging two exports.

**Replacing a video changes its `video_id`.** The row is deleted and a
new one inserted, so the identifier advances. Anything holding a
`video_id` across a replace — a bookmark, an external reference — will
be pointing at nothing.

## Recomputing global persons

```bash
docker compose run --rm global-identity-linker
```

It takes no arguments: everything in the database is its input.

Each run clears every global person and rebuilds them from scratch, so
the result depends only on what is in the database, never on the order
videos were imported. That is also why it is not automatic — it is
corpus-wide, and it gets better the more videos are loaded, so the
moment to run it is after a batch of imports rather than during one.

Interrupting it is safe. The clear and the rebuild are one transaction.

## Upgrading the schema on an existing volume

`schema.sql` runs **only when the database's data directory is empty** —
that is how the Postgres image works. On a volume that already holds
data, editing `schema.sql` and restarting changes nothing.

**Re-running the whole file is not the way to do it.** The indexes in
`schema.sql` are declared `IF NOT EXISTS` and re-run cleanly, but the
thirteen `CREATE TABLE` statements are not: on a populated database each
one fails with `relation "…" already exists`. `psql` continues past
those, so a genuinely new object would still be created — but thirteen
errors is not a signal anyone should learn to ignore.

Apply the specific change instead. To add a table:

```bash
docker compose exec -T pgvector-db psql -U duui -d duui_video_emotion \
  -c 'CREATE TABLE IF NOT EXISTS my_new_table (…);'
```

To change a table that already exists, write the `ALTER` by hand. There
is no migration tooling here, and nothing tracks which changes have been
applied.

The alternative is to start over: `docker compose down -v`, then `up`,
then re-import. That is the reliable path when the schema has changed
shape rather than grown, and it is what every phase of the cleanup has
used.

## Renaming the Compose project

Volume names are derived from the project name, so renaming it orphans
the existing volumes — the stack comes back up empty, with the old data
still on disk under the old names.

If the data does not matter, tear down **before** renaming:

```bash
docker compose down -v      # while the old name is still in effect
```

Then rename and bring it back up. If the data does matter, move it
across with a dump and restore, as below.

## Backup and restore

The database:

```bash
docker compose exec -T pgvector-db \
  pg_dump -U duui -Fc duui_video_emotion > duui-backup.dump
```

To restore into an empty database:

```bash
docker compose exec -T pgvector-db \
  pg_restore -U duui -d duui_video_emotion < duui-backup.dump
```

The video store is separate and is not in that dump. By default it is a
Docker volume; the simplest way to keep it somewhere you can copy is to
point `DUUI_VIDEO_STORE` at a host directory.

A dump does not include the videos, and the videos do not include the
rows. Restoring one without the other gives a webapp that lists videos
it cannot play, or a store of files nothing references.

## Knowing what the images were built on

The four Dockerfiles build on floating tags — `python:3.14-slim`,
`pgvector/pgvector:pg18`, and `node:24-trixie-slim` for the checker
image. That is deliberate: a rebuild picks up security updates to the
base, which is what a pinned digest would freeze.

The cost is that two builds a month apart are not the same build, and
nothing would say so. `docker-images.lock` at the project root records
the digests, and is refreshed by hand:

```bash
tests/refresh-image-digests.sh
```

**Nothing reads that file.** It is a record, not a pin: it says what a
build used, and does not make the next one match. If a rebuild starts
behaving differently, a diff of this file across commits is the first
place to look.

The Python dependencies are not locked either. They carry
floor-and-ceiling ranges and are resolved at build time, so the same
question about them is answered with `pip freeze` inside two images and
a diff, rather than from a file.

## Continuous integration

The workflow lives at the **repository root**, outside this project, at
`.github/workflows/duui-video-emotion-visualization.yml`. GitHub only
runs workflows from that location, so it cannot live in this directory.

It does not travel with the project. Copying this directory elsewhere
leaves the workflow behind, and moving or renaming the directory breaks
the `paths:` filters that scope it — the repository root holds a dozen
unrelated projects, and those filters are what keep this project's CI
from running for all of them.

It runs the same two commands you would run locally: the lint service,
then the test service.
