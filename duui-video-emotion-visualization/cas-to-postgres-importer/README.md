# cas-to-postgres-importer

Reads CAS files into the database, and puts the video each one describes into
the video store.

It is a job, not a server: it runs, does the work, and exits. One transaction
per file, so a malformed CAS costs that file and not the rest of the batch, and
the exit status is non-zero if any file failed.

A CAS is expected to sit beside its video, under the filename the CAS itself
records. If no such file is there, the importer recovers the video from the CAS
instead.

## Running it

From the stack root, with the database up:

```bash
docker compose run --rm cas-to-postgres-importer
```

That imports everything in the input directory. Naming paths imports those
instead — any mix of files and directories, given as paths *inside* the
container:

```bash
docker compose run --rm cas-to-postgres-importer /data/input/xmi/one.xmi
```

A CAS whose video is already in the database is skipped by default, without
being loaded at all, so re-running over a growing input directory is cheap.
`--on-existing replace` deletes that video and everything under it and imports
fresh:

```bash
docker compose run --rm cas-to-postgres-importer --on-existing replace
```

[operations.md](../docs/operations.md) has the rest, including what a replace
costs.

### Without the rest of the stack

The image builds from this directory alone:

```bash
docker build -t duui-video-emotion-visualization/cas-to-postgres-importer .
```

Running it needs a database carrying the schema, wherever that is. Point
`DUUI_DB_HOST` and the other credentials at it, mount the input and the video
store, and give the container paths as arguments.

Natively, on Python 3.14 with `requirements.txt` installed, `src` is the
source root rather than a package:

```bash
PYTHONPATH=src python -m importer path/to/file.xmi
```

## Configuring it

Values, defaults and precedence are all in
[configuration.md](../docs/configuration.md). This job reads:

| | |
| --- | --- |
| Input | `DUUI_INPUT_XMI_DIR`, `DUUI_INPUT_VIDEO_DIR`, `DUUI_XMI_FILE` |
| Output | `DUUI_VIDEO_DIR` — the video store |
| Behavior | `DUUI_ON_EXISTING`, `DUUI_VIDEO_VIEW` |
| Typesystems | `DUUI_TS_IDENTITY_EMOTION`, `DUUI_TS_MULTIMODAL_IDENTITY`, `DUUI_TS_EMOTION` |
| Database | `DUUI_DB_NAME`, `DUUI_DB_USER`, `DUUI_DB_PASSWORD`, `DUUI_DB_HOST`, `DUUI_DB_CONNECT_TIMEOUT` |

`--on-existing` on the command line overrides `DUUI_ON_EXISTING` for that run.

The three typesystem descriptors ship inside the image, in
`src/resources/typesystems/`. They belong to the pipeline version the image was
built for, which is why they travel with it rather than being mounted.

## Testing it

From the stack root:

```bash
docker compose run --rm tests cas-to-postgres-importer/tests
```

The suite covers the parsers against the CAS in `src/resources/sample-input/`,
including one test that imports it end to end and asserts the row counts it
produces. The database-backed tests run against the empty database the runner
provisions; run `pytest` some other way and they skip, which the summary says
in as many words.

## Where the detail is

- **The layout.** `src/importer/` is the package: `pipeline.py` runs a file,
  `parsers/` holds one module per annotation family, `cas/` holds everything
  that knows about UIMA — the typesystem, the views, the type names, and how a
  person reference is resolved. `inputs.py` expands the paths,
  `video_files.py` places the video, `job_runs.py` reports progress.
- **The schema it writes** — [database.md](../docs/database.md).
- **The contracts it shares with the other parts** — the database, the video
  store, the environment variables, and job status reporting —
  [architecture.md](../docs/architecture.md).
