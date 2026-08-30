# Configuration

Every setting, in one place. Each is an environment variable read either
by application code or by `docker-compose.yml`, and the difference
matters: six of them do not appear in the source at all.

Copy `.env.example` to `.env` and set what you need. Compose reads that
file automatically; a native run reads the same names from the
environment. Nothing here has to be set for the shipped sample to work.

Where a setting expresses a contract between sub-projects rather than a
value, [architecture.md](architecture.md) explains the contract.

## What `.env` can and cannot change

Compose passes a variable into a container only where
`docker-compose.yml` names it. Nineteen of the settings below are
interpolated from the environment and can therefore be set in `.env`.
**Nine cannot**, and are marked below:

    DUUI_DB_HOST      DUUI_TS_EMOTION              DUUI_QUERY_MAX_ROWS
    DUUI_VIDEO_DIR    DUUI_TS_IDENTITY_EMOTION     DUUI_QUERY_MAX_TOOL_ITERATIONS
    DUUI_XMI_FILE     DUUI_TS_MULTIMODAL_IDENTITY  DUUI_QUERY_STATEMENT_TIMEOUT_MS

Two of those are deliberate: `DUUI_DB_HOST` and `DUUI_VIDEO_DIR` are
fixed to the service name and the container path, which is what makes
the stack wire itself together. The other seven are simply not passed
through. Setting them in `.env` has no effect on a container; changing
them means editing `docker-compose.yml`, or running outside Docker.

## Input and output paths

Read by the importer, except the last, which the webapp also reads.

| Variable | Default | What it does |
| --- | --- | --- |
| `DUUI_INPUT_XMI_DIR` | `cas` | Where the importer looks for CAS files when given no path. |
| `DUUI_INPUT_VIDEO_DIR` | follows `DUUI_INPUT_XMI_DIR` | Where the video files those CAS files name are. Unset, it is wherever the CAS files are, so one directory of pipeline output needs one setting rather than two. |
| `DUUI_XMI_FILE` | unset | A single file to import when no path is given. Unset, the whole input directory is imported. **Not settable in `.env`.** |
| `DUUI_VIDEO_DIR` | `cas` | The video store: where the importer puts a video and where the webapp reads it. **Not settable in `.env`** — Compose fixes it at the container path. |

The two input directories are read-only to the importer. It never writes
back to where your pipeline output lives.

## Database

Read by all three sub-projects, which is what lets one value reach three
containers that share no code.

| Variable | Default | What it does |
| --- | --- | --- |
| `DUUI_DB_NAME` | `your_db` | Database name. |
| `DUUI_DB_USER` | `your_user` | User. |
| `DUUI_DB_PASSWORD` | `your_password` | Password. |
| `DUUI_DB_HOST` | `localhost` | Host. **Not settable in `.env`** — Compose fixes it at the database service's name. |
| `DUUI_DB_CONNECT_TIMEOUT` | `10` | Seconds to wait for the *connection*. It never bounds a query that is already running. |

**The three credential defaults cannot connect to anything.** That is
what they are for: a run with nothing configured fails to reach a
database rather than reaching an unintended one. Compose supplies
working values, so this only bites a native run.

Raise the connect timeout for a slow or distant database. Without one,
a host that accepts the route but never answers hangs the caller for
minutes with nothing printed.

## Importer behavior

| Variable | Default | What it does |
| --- | --- | --- |
| `DUUI_ON_EXISTING` | `skip` | What to do with a CAS whose video is already imported. `skip` leaves it alone without even loading the file; `replace` deletes the existing video and everything under it, then imports fresh. Overridable per run with `--on-existing`. |
| `DUUI_VIDEO_VIEW` | `_InitialView` | Which sofa holds the video, for a CAS that carries one embedded. Any other `video/*` sofa is used as a fallback, so this only needs setting when a pipeline routes the video somewhere unexpected. |
| `DUUI_TS_IDENTITY_EMOTION` | the bundled file | Path to a typesystem descriptor. **Not settable in `.env`.** |
| `DUUI_TS_MULTIMODAL_IDENTITY` | the bundled file | Path to a typesystem descriptor. **Not settable in `.env`.** |
| `DUUI_TS_EMOTION` | the bundled file | Path to a typesystem descriptor. **Not settable in `.env`.** |

The three typesystem files ship inside the importer image, matching the
pipeline version it was built for. Override them only to read a CAS from
a pipeline that used different ones.

## Identity linking

| Variable | Default | What it does |
| --- | --- | --- |
| `DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD` | `0.30` | Maximum cosine distance at which two face embeddings are taken to be the same person. Lower is stricter. |
| `DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD` | `0.35` | The same, for voice embeddings. Faces are compared first; voices are only reached for a person the face pass did not match. |

pgvector's cosine distance is 0 for identical vectors and 2 for opposite
ones. No derivation for either default is recorded in this repository.

## Webapp

The Ask panel talks to an OpenAI-compatible chat-completions endpoint.
Leave the key empty and the panel reports itself as unconfigured while
everything else works unchanged.

| Variable | Default | What it does |
| --- | --- | --- |
| `DUUI_QUERY_API_KEY` | empty | The key. Empty disables the panel. |
| `DUUI_QUERY_BASE_URL` | a university-hosted gateway | Any OpenAI-compatible endpoint. |
| `DUUI_QUERY_MODEL` | `gondor.qwen3-vl:32b` | Model name, as that endpoint knows it. |
| `DUUI_QUERY_MAX_ROWS` | `500` | Row cap on a query the model writes. **Not settable in `.env`.** |
| `DUUI_QUERY_STATEMENT_TIMEOUT_MS` | `8000` | How long one of those queries may run. **Not settable in `.env`.** |
| `DUUI_QUERY_MAX_TOOL_ITERATIONS` | `6` | How many turns the model gets before the attempt is abandoned. **Not settable in `.env`.** |

## Read by Compose only

These six are not in the source. Setting them in the environment of a
native run does nothing.

| Variable | Default | What it does |
| --- | --- | --- |
| `DUUI_WEBAPP_HOST_PORT` | `8010` | Host port the webapp is published on. Inside the container it is always 8000. |
| `DUUI_DB_HOST_PORT` | `5432` | Host port the database is published on. Change it if you already run a Postgres. |
| `DUUI_VIDEO_STORE` | `video_media` | The video store volume. Set it to an absolute host path to keep the videos outside Docker. |
| `DUUI_TEST_DB_NAME` | `duui_video_emotion_test` | The database the test runner creates and uses. Separate, so a test run cannot touch real data. |
| `DUUI_TEST_UID` | `1000` | The uid the test container runs as, so files it writes belong to you. |
| `DUUI_TEST_GID` | `1000` | The matching gid. |
