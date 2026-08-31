# DUUI Video Emotion Visualization

Browse videos annotated by a DUUI pipeline: transcripts, per-modality emotion
readings, on-screen people, and the same person recognized across videos.

## The four parts

| | What it does |
| --- | --- |
| [`pgvector-db`](pgvector-db/README.md) | Postgres with pgvector, and the schema |
| [`cas-to-postgres-importer`](cas-to-postgres-importer/README.md) | Reads CAS `.xmi` files into the database and copies their videos into the video store |
| [`global-identity-linker`](global-identity-linker/README.md) | Links people across videos by face and voice embeddings |
| [`webapp`](webapp/README.md) | The web interface: a FastAPI backend and a static frontend |

They share no code. The database is the only thing they have in common — see
[`docs/architecture.md`](docs/architecture.md).

## Running it

Requires Docker, and nothing else: every part runs in a container, including
the tests. The images are built on Python 3.14 and Postgres 18, which is what
a run outside Docker would have to match.

```bash
docker compose up -d
```

That starts the database and the webapp, which is then at
<http://localhost:8010>. It imports nothing, so the video list is empty until
you ask for an import.

The two batch jobs are held behind Compose profiles so they never run as a side
effect of `up`. Naming one directly activates its profile:

```bash
docker compose run --rm cas-to-postgres-importer
docker compose run --rm global-identity-linker
```

The first loads CAS files into the database. The second works out which people
appear in more than one video, over the whole corpus at once, so it is worth
running after a batch of imports rather than during one.

*If your Compose does not recognize the service, add `--profile import` or
`--profile identity`. Older versions did not activate a profile from `run`.*

## Pointing it at your own material

Copy `.env.example` to `.env`. With nothing set, the importer reads the sample
CAS that ships inside its own image. Two settings point it at yours instead:

```ini
DUUI_INPUT_XMI_DIR=/absolute/path/to/xmi
DUUI_INPUT_VIDEO_DIR=/absolute/path/to/videos
```

Both are mounted read-only, so nothing is moved or modified where it already
lives. Leave the second unset when the videos sit beside the CAS files.

Every other setting — ports, credentials, thresholds, the Ask panel — is in
[`docs/configuration.md`](docs/configuration.md).

## Tests

```bash
docker compose run --rm tests
```

Anything after `tests` is passed straight to pytest:

```bash
docker compose run --rm tests webapp/tests -k contrast
```

This is the supported way to run the whole suite; [`tests/`](tests/README.md)
says why, and what else lives in there. The one documented exception is the
accessibility subset, which needs no database and no dependencies and has its
own path in [`webapp/docs/accessibility.md`](webapp/docs/accessibility.md).

Continuous integration runs the same checks. The workflow lives at the
repository root, outside this project, which has consequences if the project is
ever moved — [`docs/operations.md`](docs/operations.md) has them.

## Documentation

[`docs/`](docs/README.md) is the map: architecture, configuration, the schema,
operations, the glossary, and the writing style. Each sub-project's own README
is linked from the table above.
