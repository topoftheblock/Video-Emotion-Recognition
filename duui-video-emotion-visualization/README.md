# DUUI Video Emotion Visualization

Browse videos annotated by a DUUI pipeline: transcripts, per-modality emotion
readings, on-screen people, and the same person recognized across videos.

> **The documentation is being rebuilt.** This page is deliberately short until
> that work finishes. Start at [`docs/`](docs/README.md).

## The four parts

| | What it does |
| --- | --- |
| [`pgvector-db`](pgvector-db/) | Postgres with pgvector, and the schema |
| [`cas-to-postgres-importer`](cas-to-postgres-importer/) | Reads CAS `.xmi` files into the database and copies their videos into the video store |
| [`global-identity-linker`](global-identity-linker/) | Links people across videos by face and voice embeddings |
| [`webapp`](webapp/) | The web interface: a FastAPI backend and a static frontend |

They share no code. The database is the only thing they have in common.

## Running it

Requires Docker.

```bash
docker compose up -d
```

That starts the database and the webapp, which is then at
<http://localhost:8010>. The two batch jobs are held behind Compose profiles so
they never run by accident:

```bash
docker compose --profile import run --rm cas-to-postgres-importer
```

```bash
docker compose --profile identity run --rm global-identity-linker
```

Copy `.env.example` to `.env` to change ports, credentials, or where the
importer looks for input.

## Tests

```bash
.venv/bin/python -m pytest
```

Tests that need a database skip without one. They currently expect an empty
database and report failures against a populated one.

## Documentation

[`docs/`](docs/README.md) — architecture, configuration, the schema, operations,
the glossary, and the writing style. [`docs/plan/`](docs/plan/README.md) tracks
the rebuild.
