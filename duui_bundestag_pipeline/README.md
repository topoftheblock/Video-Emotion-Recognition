# DUUI Bundestag Video-Emotion CAS Parser

Parses UIMA CAS XMI output from the DUUI video-emotion pipeline into a
Postgres database.

## Project layout

```
.
├── main.py                # CLI entry point
├── Dockerfile             # one-off CAS importer image (docker compose run importer)
├── docker-compose.yml     # db + webapp + importer services
├── duui_parser/           # the parser package
├── webapp/                # video review viewer (subtitles, emotions, bounding boxes)
├── schema/                # database schema (schema.sql + docs)
├── typesystems/           # UIMA typesystem XML files (see below)
└── cas/                   # input .xmi files to parse, and the actual video files
```

## 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Set up PostgreSQL

You need a Postgres server with the **pgvector** extension available
(the schema stores face/voice embeddings as native `vector` columns).

**Install Postgres + pgvector:**
- macOS (Homebrew): `brew install postgresql@16 pgvector`
- Ubuntu/Debian: `sudo apt install postgresql postgresql-16-pgvector` (package name varies by Postgres version -- see https://github.com/pgvector/pgvector#installation)
- Docker (simplest if you don't want a local install): `docker run -d --name duui-postgres -e POSTGRES_PASSWORD=yourpassword -p 5432:5432 pgvector/pgvector:pg16`

**Create the database and load the schema:**
```bash
createdb duui_bundestag
psql -d duui_bundestag -f schema/schema.sql
```
`schema/schema.sql` runs `CREATE EXTENSION IF NOT EXISTS vector;` itself, so as long as pgvector is installed on the server, no separate extension setup step is needed.

Verify it worked:
```bash
psql -d duui_bundestag -c "\dt"
```
You should see 15 tables (`videos`, `models`, `persons`, ... down to `emotion_fusion_references`).

## 3. Get the typesystem files

`typesystems/` must contain the three type-system descriptor XML files
that the Java DUUI pipeline used to produce your CAS:

- `IdentityEmotionTypeSystem.xml`
- `MultimodalIdentityTypeSystem.xml`
- `EmotionTypeSystem.xml`

These come from the pipeline project itself, not from this repo --
usually under something like `src/main/resources/` or `desc/type/` in
the Java project. Note: these three files turned out to overlap
heavily (see `duui_parser/typesystem.py`'s docstring) and reference a
handful of types (`MultimediaElement`, `AudioToken`, `MetaData`,
`Embedding`) that live in external shared typesystem imports not
included in any of the three -- the parser handles both cases
automatically (de-duplication + fallback type definitions), so you
don't need to track down the missing imports yourself.

Drop the three files into `typesystems/`.

## 4. Add your CAS file

Put the `.xmi` file you want to parse into `cas/`.

## 5. Configure

```bash
cp .env.example .env
```

Edit `.env` with your real database credentials and confirm the file
paths match what you placed in steps 3-4. Everything in `.env` maps
directly to `duui_parser/config.py`, so if you'd rather not use a
`.env` file, exporting the same variables in your shell/CI works
identically.

## 6. Run

```bash
python main.py                    # uses DUUI_XMI_FILE from .env
python main.py cas/other_file.xmi # or pass a path explicitly
```

This loads and patches the typesystem, loads the CAS (lenient mode --
annotation types outside this parser's scope, e.g. linguistic
Token/POS/Dependency layers, are safely skipped), runs every parser
step in `duui_parser/parsers/PARSE_STEPS`, and commits the result in a
single transaction (rolled back automatically if any step raises).

## Processing multiple CAS files

For a batch of files, loop over `run()` rather than calling `main.py`
repeatedly -- this avoids reloading and re-patching the typesystem for
every file:

```python
from pathlib import Path
from duui_parser.pipeline import run

for xmi_path in Path("cas").glob("*.xmi"):
    run(str(xmi_path))
```

If this grows into a real batch job, it's worth having `run()` accept
an already-loaded typesystem instead of reloading it every call --
happy to add that if you get there.

## Web viewer

`webapp/` is a small video review tool: pick an imported video, play
it, and see subtitles, per-modality emotions, and face/person
bounding boxes rendered in sync with playback -- all read live from
Postgres, nothing pre-rendered into the video file itself.

**Setup:**

1. Put the actual video file(s) in the directory named by
   `DUUI_VIDEO_DIR` in `.env` (defaults to `cas/`), with the filename
   matching each row's `videos.filename` column exactly (e.g. if the
   DB says `filename = 'first2.mp4'`, the file must be at
   `cas/first2.mp4`). The database only stores metadata, never the
   video bytes.
2. Run the parser first (`python main.py`) so there's data to show.
3. Start the viewer from the project root:
   ```bash
   uvicorn webapp.server:app --reload
   ```
4. Open http://127.0.0.1:8000 -- pick a video from the dropdown in the
   top bar.

**How the syncing works** (`webapp/server.py` + `webapp/static/app.js`):
- *Subtitles*: sentence-level `segments` rows don't store their own
  text, so the backend reconstructs each sentence's caption by joining
  every `linguistic_tokens.word` whose `start_time` falls inside that
  sentence's `[start_time, end_time]` window (matched by time overlap,
  not `linguistic_tokens.segment_id` -- confirmed against real data
  that FK isn't always populated by the source annotator).
- *Bounding boxes*: `face_detections`/`person_detections` are sampled
  per-frame, so the frontend finds whichever detection is nearest to
  the current playback time (within a 150 ms tolerance) and draws it
  scaled to the video's displayed size (`x/y/w/h` are normalized
  0..1, so this works regardless of the video's native resolution).
- *Video-modality emotion labels on boxes*: `base_emotions` rows don't
  carry their own bounding box -- they share `frame_index` with the
  detection they were computed from, which is the join used to attach
  a label (e.g. "SURPRISE") to the right box.
- *Voice panel*: whichever `audio`-modality `base_emotions` row covers
  the current time drives the label + valence/arousal bars.
- *Text-emotion badge*: same idea for `text`-modality rows, shown next
  to the subtitle.

**Multiple people / longer videos**: the current version loads the
full per-video payload in one request, which is fine for short clips
but would get large for an hour-long session with dense per-frame
detections. If you outgrow that, the natural next step is adding
`?start=&end=` windowing to `/api/videos/{id}/data` and having the
frontend fetch a rolling window around the current playback time
instead of everything up front -- happy to add that when you have a
longer real file to test it against.

## Importing a CAS file (Docker)

If you're running the stack via `docker compose` (see `docker-compose.yml`)
rather than a local venv, importing a new CAS doesn't need Python/
`dkpro-cassis` installed on the host at all -- there's a dedicated
`importer` service for it, built from the root `Dockerfile`.

It's deliberately **not** part of the webapp container: `webapp/Dockerfile`
only installs `webapp/requirements.txt` (FastAPI, psycopg2, openai --
no `dkpro-cassis`/lxml) to keep that image small, since `webapp/server.py`
never parses CAS files itself, only reads what's already in Postgres.
The importer is a separate one-off job, not a long-running service, so
it's excluded from `docker compose up` by the `import` profile and only
runs when invoked explicitly.

**What to mount** (already wired up in `docker-compose.yml`):
- `./cas:/app/cas` -- both the `.xmi` file you're importing and the
  matching video file live here; same directory the `webapp` service
  mounts read-only as `/videos` (see step 4 below for why the names
  have to match).
- `./typesystems:/app/typesystems:ro` -- the three typesystem XML
  files from step 3 above.

**Env vars the importer container needs** (already set by
`docker-compose.yml`'s `importer.environment` block -- only relevant
if you're running the built image directly instead of through compose):
- `DUUI_DB_HOST=db` -- the Postgres service's name on the compose
  network, **not** `localhost` (that only works when running `main.py`
  on the host against the container's exposed port 5432).
- `DUUI_DB_NAME`, `DUUI_DB_USER`, `DUUI_DB_PASSWORD` -- must match the
  `db` service's `POSTGRES_*` values (`duui_bundestag`/`duui`/`duui`).
- `DUUI_TS_IDENTITY_EMOTION`, `DUUI_TS_MULTIMODAL_IDENTITY`,
  `DUUI_TS_EMOTION` -- only needed if your typesystem filenames differ
  from the defaults in `duui_parser/config.py` (`typesystems/*.xml`).

**Entrypoint**: the image's `ENTRYPOINT` is `python main.py`, so you
only ever pass the CAS path as the command:

```bash
docker compose up -d db                         # wait for it to become healthy
docker compose run --rm importer cas/your_file.xmi
docker compose up -d webapp
```

Re-running against a file you already imported is safe -- see the
`UNIQUE (emotion_id, label)` / `ON CONFLICT ... DO NOTHING` note at the
bottom of this README.

**Filename matching still applies**: whatever file the CAS references
as its source video needs to exist in `cas/` under that exact name --
same requirement as the non-Docker path in "Web viewer" above, since
`videos.filename` is what both the importer and the webapp key off of.

## Natural-language query agent

The "Ask" bar above the player lets you type a question like *"give me
the video sequences where video emotion and text emotion diverge"*
instead of writing SQL by hand. Under the hood (`duui_parser/query_agent/`):

1. **`schema_context.py`** gives the model a schema description with the
   domain semantics that aren't recoverable from column names alone
   (which modality pairs with which granularity, how to compare
   emotions across modalities via the sentence they fall inside, how
   to get a display name for a person, etc.), plus a worked example
   for cross-modal "divergence" questions.
2. **`agent.py`** runs a tool-use loop against an OpenAI-compatible
   chat-completions endpoint (`openai` SDK, custom `base_url` --
   this project points it at a university-hosted Qwen3-VL gateway, not
   Anthropic): the model calls `run_sql` to explore/validate candidate
   queries against a preview (20 rows + count), then calls
   `submit_answer` once with the final query, a plain-language
   explanation, and the set of display **overlays** relevant to that
   question (`transcript`, `bounding_boxes`, `video_emotion`,
   `audio_emotion`, `text_emotion`, `fused_emotion`).
3. **`sql_guard.py`** re-executes only that final, validated query
   itself (never trusting rows the model claims to have seen) --
   single `SELECT`/`WITH` statement only, run inside a Postgres
   `READ ONLY` transaction with a statement timeout and a row cap.

`POST /api/ask {"question": "..."}` (see `webapp/server.py`) returns
the SQL, explanation, overlays, and result rows; rows exposing
`video_id`/`start_time`/`end_time` are turned into clickable "jump to
this clip" segments. Clicking one seeks the player to that moment and
switches the frontend into showing *only* the overlays the agent
picked -- e.g. a divergence question shows the transcript plus the
video- and text-emotion labels, and hides the voice panel and fused
readout, since those weren't asked about. "Reset view" clears this and
goes back to showing everything.

Requires `DUUI_QUERY_API_KEY` in `.env`. `DUUI_QUERY_BASE_URL` and
`DUUI_QUERY_MODEL` default to the university Qwen3-VL gateway this
project was built against -- point them at a different OpenAI-compatible
provider/model if needed (`DUUI_QUERY_MAX_ROWS`,
`DUUI_QUERY_STATEMENT_TIMEOUT_MS` are the other, optional, knobs).
Note this particular model is slow: a single question can take several
minutes (multi-step tool use against a large model, no progress
indicator in the UI yet) -- that's expected, not a hang.

## Database schema

`schema/schema.sql` is the authoritative schema (also documented in
`schema/data_schema_with_types.md`); the parser's INSERT statements
are written to match it exactly: `videos`, `models`, `global_persons`,
`persons`, `segments`, `linguistic_tokens`, `face_embeddings`,
`voice_embeddings`, `presences`, `face_detections`,
`person_detections`, `base_emotions`, `emotion_scores`,
`fused_emotions`, `emotion_fusion_references`. The parser does not
create these tables -- run `schema/schema.sql` once before the first
import (see step 2 above).

One addition was made relative to the schema.sql you may have
originally: `emotion_scores` now has `UNIQUE (emotion_id, label)`,
since the parser relies on that for `ON CONFLICT (emotion_id, label)
DO NOTHING` to make re-running the pipeline on the same file
idempotent.
