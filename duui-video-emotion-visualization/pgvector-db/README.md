# pgvector-db

Postgres with the pgvector extension, carrying this project's schema.

The image is `pgvector/pgvector:pg18` plus one file: `schema.sql`, copied into
`/docker-entrypoint-initdb.d/`. Running the image is therefore enough to get an
initialized database, with no separate step to remember.

It is the only thing the other three sub-projects share. They never call each
other; what one writes, another reads, and the schema is the whole of the
agreement between them.

## Running it

From the stack root, as part of everything else:

```bash
docker compose up -d
```

Or on its own — the image builds from this directory alone, and needs only the
three variables the upstream image already defines:

```bash
docker build -t duui-video-emotion-visualization/pgvector-db .
docker run --rm -e POSTGRES_DB=duui_video_emotion -e POSTGRES_USER=duui \
  -e POSTGRES_PASSWORD=duui duui-video-emotion-visualization/pgvector-db
```

Add `-p 5432:5432` to reach it from the host as well as from other containers.

Compose supplies those three from `DUUI_DB_NAME`, `DUUI_DB_USER` and
`DUUI_DB_PASSWORD`, which is how one setting reaches both the database and the
sub-projects that connect to it.

## The one thing to know

**`schema.sql` runs only when the data directory is empty.** That is how the
upstream image works, and it has a consequence worth stating plainly: on a
volume that already holds data, editing this file and restarting changes
nothing at all.

[operations.md](../docs/operations.md) has what to do instead, and why the
`job_runs` table is also created by three of the services rather than by this
file alone.

## Not a Python project

No `src/`, no `tests/`, no `pyproject.toml`. This is a database image, and the
sub-project layout the other three follow would be empty scaffolding here. The
schema is exercised by their suites, which run against a database built from
this image.

## Where the detail is

- **The schema, table by table** — [database.md](../docs/database.md).
- **Why the database is the integration point** —
  [architecture.md](../docs/architecture.md).
