# DUUI Bundestag Video-Emotion CAS Parser

Parses UIMA CAS XMI output from the DUUI video-emotion pipeline into a
Postgres database.

## Quickstart (Docker)

Requires only Docker. Drop your pipeline output into `cas/` -- each CAS
`.xmi` next to the video file it references (see
`cas/full_2sek_with_person.xmi` / `cas/first2.mp4` for a small example
pair already in this repo). Then:

```bash
docker compose up -d db                    # start Postgres; wait ~10s for it to report healthy
docker compose run --rm importer cas/      # import every .xmi in cas/ + place their videos
docker compose up -d webapp                # start the viewer
```

Open **http://localhost:8010**.

The importer takes a whole directory (above), a single file
(`... importer cas/one_file.xmi`), or any mix of both -- so you can
import a batch in one command and add more later without restarting
anything. `db`/`webapp` only need starting once.

Everything below this is either the no-Docker (local Python + Postgres)
setup, or a deeper explanation of the Docker path -- see
"Configuration reference" for every env var and port, and
"Docker architecture" for what those three commands actually do and how
to recover if a video didn't get placed.

## Prerequisites

**Docker path**: Docker (with Compose v2) and nothing else. No Python,
no Postgres, no **ffmpeg**, no system libraries on the host -- the
images install everything themselves, and nothing in this codebase
shells out to an external binary (no `ffmpeg`/`subprocess` calls
anywhere; videos are streamed byte-for-byte as-is, never transcoded).
The upstream DUUI pipeline that *produces* the CAS files does need
ffmpeg and GPUs, but that's a separate project -- this repo only
consumes its output.

**Non-Docker path**: Python 3.12, and Postgres 16+ with the
**pgvector** extension available (the schema stores face/voice
embeddings as native `vector` columns). See steps 1-2 below.

**Optional**: the NLP enrichment step needs a spaCy German model
(~13 MB download, off by default) -- see "Post-processing" below.

## Configuration reference

Every setting is an environment variable, read either from `.env` (see
`.env.example`) or the real environment -- `duui_parser/config.py` is
the single place they're all defined. With `docker compose`, the ones
marked *(compose)* are read on the **host** to build the compose file;
the rest are passed into the containers.

**Ports** *(compose)* -- change these if something already occupies
them on your machine:

| Variable | Default | What it is |
| :--- | :--- | :--- |
| `DUUI_WEBAPP_HOST_PORT` | `8010` | Host port for the viewer (container always listens on 8000) |
| `DUUI_DB_HOST_PORT` | `5432` | Host port for Postgres. Set this if you already run a local Postgres. Containers reach the DB as `db:5432` regardless |

**Where files live** *(compose, except `DUUI_INPUT_DIR`/`DUUI_VIDEO_DIR`)*:

| Variable | Default | What it is |
| :--- | :--- | :--- |
| `DUUI_INPUT_HOST_DIR` | `./cas` | Host directory holding the pipeline's output (`.xmi` files + their videos). Point this wherever your pipeline writes |
| `DUUI_TYPESYSTEMS_HOST_DIR` | `./typesystems` | Host directory with the three typesystem XMLs |
| `DUUI_VIDEO_STORE` | `video_media` | Where imported videos are stored. A plain name = Docker named volume; a host path = bind mount (use that if you want to browse/back up the video store directly) |
| `DUUI_INPUT_DIR` | `cas` (`/app/cas` in Docker) | Directory the importer *reads* -- a no-argument import processes every `.xmi` in it |
| `DUUI_VIDEO_DIR` | `cas` (`/media` in Docker) | Directory the importer *writes* videos into and the webapp *serves* them from |
| `DUUI_XMI_FILE` | *(unset)* | Optional: if set, a no-argument import does just this one file instead of all of `DUUI_INPUT_DIR` |
| `DUUI_TS_IDENTITY_EMOTION`<br>`DUUI_TS_MULTIMODAL_IDENTITY`<br>`DUUI_TS_EMOTION` | `typesystems/*.xml` | Only needed if your typesystem filenames differ |

**Database**:

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DUUI_DB_NAME` | `your_db` | compose sets `duui_bundestag` |
| `DUUI_DB_USER` | `your_user` | compose sets `duui` |
| `DUUI_DB_PASSWORD` | `your_password` | compose sets `duui` |
| `DUUI_DB_HOST` | `localhost` | **`db`** inside compose (the service name); `localhost` only when running `main.py` on the host |

**Natural-language "Ask" panel** (optional -- leave the key empty and
everything else still works, the panel just reports it's unconfigured):

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DUUI_QUERY_API_KEY` | *(empty)* | Any OpenAI-compatible endpoint's key. Empty = feature disabled |
| `DUUI_QUERY_BASE_URL` | `https://lehre.llm.texttechnologylab.org/api` | Swap for a different provider |
| `DUUI_QUERY_MODEL` | `gondor.qwen3-vl:32b` | |
| `DUUI_QUERY_MAX_ROWS` | `500` | Row cap on agent queries |
| `DUUI_QUERY_STATEMENT_TIMEOUT_MS` | `8000` | Per-query timeout |
| `DUUI_QUERY_MAX_TOOL_ITERATIONS` | `6` | How many SQL attempts the agent gets |

**Post-processing steps** (all run automatically on import -- see
"Post-processing" below):

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DUUI_ENABLE_GLOBAL_PERSON_LINKING` | `true` | Cross-video person identity via pgvector |
| `DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD` | `0.30` | Cosine distance; lower = stricter |
| `DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD` | `0.35` | |
| `DUUI_ENABLE_EMOTION_FUSION` | `true` | Per-sentence multimodal fusion |
| `DUUI_ENABLE_NLP_ENRICHMENT` | `false` | POS/NER backfill; needs `requirements-nlp.txt` |
| `DUUI_SPACY_MODEL` | `de_core_news_sm` | |

### Building / running the containers separately

You don't need compose. Both images build from the **repo root** as
build context (the webapp image also copies `duui_parser/`, which
`webapp/server.py` imports):

```bash
docker build -f Dockerfile -t duui-importer .
docker build -f webapp/Dockerfile -t duui-webapp .
```

Running them standalone means supplying by hand what compose otherwise
wires up -- network, mounts, and env vars:

```bash
# Importer: ENTRYPOINT is `python main.py`, so the command is just paths
# (or nothing at all, to import everything in DUUI_INPUT_DIR).
docker run --rm \
  -e DUUI_DB_HOST=my-postgres -e DUUI_DB_NAME=duui_bundestag \
  -e DUUI_DB_USER=duui -e DUUI_DB_PASSWORD=duui \
  -e DUUI_INPUT_DIR=/app/cas -e DUUI_VIDEO_DIR=/media \
  -v /path/to/pipeline/output:/app/cas \
  -v /path/to/typesystems:/app/typesystems:ro \
  -v duui_videos:/media \
  duui-importer

# Webapp: listens on 8000 in-container; map it wherever you like.
docker run -d --name duui-webapp -p 8010:8000 \
  -e DUUI_DB_HOST=my-postgres -e DUUI_DB_NAME=duui_bundestag \
  -e DUUI_DB_USER=duui -e DUUI_DB_PASSWORD=duui \
  -e DUUI_VIDEO_DIR=/media \
  -v duui_videos:/media:ro \
  duui-webapp
```

Both need to reach Postgres (`--network` or a reachable
`DUUI_DB_HOST`), and both must agree on the **same** video store
(`duui_videos` above) -- that's the only thing they share besides the
database. The DB itself is a stock `pgvector/pgvector:pg16` with
`schema/schema.sql` applied once.

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
├── tests/                 # pytest suite -- see "Tests" below
├── .github/workflows/     # CI (runs the test suite + Docker builds)
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
python main.py                          # uses DUUI_XMI_FILE from .env
python main.py cas/other_file.xmi       # one CAS
python main.py cas/                     # every *.xmi in that directory
python main.py a.xmi b.xmi cas/more/    # any mix of files and directories
```

For each CAS this loads it (lenient mode -- annotation types outside
this parser's scope, e.g. linguistic Token/POS/Dependency layers, are
safely skipped), runs every parser step in
`duui_parser/parsers/PARSE_STEPS`, commits in a single transaction
(rolled back automatically if any step raises), and places the video
file sitting next to it into `DUUI_VIDEO_DIR`.

## Processing multiple CAS files

Point `main.py` (or the Docker `importer`) at a **directory** and it
imports every `*.xmi` directly inside it -- the normal way to load a
batch of pipeline output:

```bash
python main.py cas/
docker compose run --rm importer cas/     # same thing, in Docker
```

Details worth knowing:

- **The typesystem is loaded and patched once per batch**, not per
  file -- that step dominates startup, so a directory import is
  substantially faster than calling `main.py` once per file.
- **Each file gets its own transaction.** A malformed CAS is reported
  and skipped, and the batch continues; you get a
  `N imported, M failed` summary at the end, with each failure listed.
  `main.py` exits non-zero if anything failed, so a script or CI job
  notices a partial import.
- **Directory scanning is not recursive** (`*.xmi` directly inside the
  given directory). A CAS and its companion video live side by side in
  one flat drop directory, so recursing would only risk pulling in
  unrelated exports -- pass several directories explicitly if you have
  more than one.
- **Re-importing is safe** -- see the `ON CONFLICT` note at the bottom
  of this README; re-running a directory after adding one new file
  re-imports the others harmlessly rather than duplicating them.

To drive it from Python instead, `run_many()` takes the same mix of
files and directories:

```python
from duui_parser.pipeline import run_many

succeeded, failed = run_many(["cas/"])
```

## Post-processing: cross-video identity, emotion fusion, NLP

Three properties of the database are computed by the parser itself,
not read off the CAS, since the real Bundestag CAS never carries this
information: they run as the last few steps in `PARSE_STEPS`
(`duui_parser/parsers/__init__.py`), automatically on every import,
each independently switchable via `.env`.

**Vector-based global person linking across videos**
(`duui_parser/parsers/global_identity.py`, `DUUI_ENABLE_GLOBAL_PERSON_LINKING`,
default on). After a video's `persons`/`face_embeddings`/
`voice_embeddings` are inserted, every person without a
`global_person_id` yet is matched by pgvector cosine distance (`<=>`)
between embedding centroids against every other already-imported
video's persons (face embeddings first, voice as a fallback). A match
below `DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD` /
`DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD` (cosine distance, lower
= stricter; defaults 0.30 / 0.35) joins an existing `global_persons`
row or creates a new one shared by both sides. This is a similarity
heuristic, not a verified identity match -- retune the thresholds
against real cross-video duplicates in your own data before trusting
it beyond suggestions. Requires the HNSW indexes in `schema.sql`
(`face_embeddings_embedding_hnsw_idx` / `voice_embeddings_embedding_hnsw_idx`)
to stay fast as more videos accumulate.

**Emotion aggregation / fusion**
(`duui_parser/parsers/emotion_fusion.py`, `DUUI_ENABLE_EMOTION_FUSION`,
default on). Runs last, after every modality's `base_emotions` rows
for the video exist. For each sentence, averages valence/arousal
within each available modality (video's many per-frame readings first,
down to one number), then across modalities, into one
`fused_emotions` row (`fusion_method = 'mean-valence-arousal-v1'`).
`dominant_label` is taken from whichever modality had the largest
valence/arousal magnitude -- a cheap heuristic, not a trained fusion
model. `emotion_fusion_references` links each fusion back to every
`base_emotions` row that went into it.

**NLP integration** (`duui_parser/parsers/nlp_enrichment.py`,
`DUUI_ENABLE_NLP_ENRICHMENT`, default **off**). Backfills
`linguistic_tokens.pos_tag`/`.ner_label` -- always NULL from the CAS
itself -- by running a German spaCy model (`DUUI_SPACY_MODEL`, default
`de_core_news_sm`) over each sentence's reconstructed text and mapping
spaCy's token/entity spans back onto our WhisperX-derived tokens by
character overlap (their tokenizations don't always agree exactly,
e.g. "Dank." as one token vs spaCy's "Dank" + "."). Off by default
because it needs an extra model download:
```bash
pip install -r requirements.txt -r requirements-nlp.txt
```
then set `DUUI_ENABLE_NLP_ENRICHMENT=true` in `.env` (or as an
importer env var in Docker -- see `docker-compose.yml`).

## Web viewer

`webapp/` is a small video review tool: pick an imported video, play
it, and see subtitles, per-modality emotions, and face/person
bounding boxes rendered in sync with playback -- all read live from
Postgres, nothing pre-rendered into the video file itself.

**Screenshots** (desktop and mobile, real Bundestag sample data, no
mockups):

<p align="center">
  <img src="docs/screenshots/overview.png" alt="Main viewer: video with face bounding box + emotion label, live subtitle, voice/people/on-screen panels" width="820"><br>
  <sub>Playback in progress -- a face bounding box tagged <code>ANGER</code>, the current subtitle, a <code>JOY</code> text-emotion badge, and the sidebar's live voice/people/on-screen readouts, all resolved for this exact video timestamp.</sub>
</p>

<p align="center">
  <img src="docs/screenshots/mobile.png" alt="Mobile layout: stacked cards, same data" width="300">
  &nbsp;&nbsp;
  <img src="docs/screenshots/ask-results.png" alt="Ask panel showing a natural-language query result with clickable jump-to-clip segments" width="500">
  <br>
  <sub>Left: the same view responsive on mobile. Right: a natural-language query's results -- SQL, explanation, overlay tags, and a scrollable list of clickable "jump to this clip" segments (see below).</sub>
</p>

**Using it** (once the stack is running, see Setup below):

Open http://localhost:8010 (or wherever you're serving it):

1. **Pick a video** -- the top-right dropdown lists every video that's
   been imported (`videos.filename`). Selecting one loads its data and
   starts the player.
2. **Watch it play** -- standard controls (play/pause, scrubber, time
   readout) at the bottom of the frame. Everything else on the page
   updates live as the video plays, synced to `currentTime`:
   - *Subtitles* burn in at the bottom of the frame, sentence by
     sentence.
   - *A text-emotion badge* appears next to the subtitle (e.g. `JOY`)
     -- the dominant emotion detected from the words themselves.
   - *Bounding boxes* are drawn over detected faces/people, each
     labeled with that box's video-modality emotion (e.g. `ANGER`) if
     available.
   - *Voice panel* (sidebar) shows the current audio-modality emotion
     plus valence/arousal bars -- emotion from tone of voice,
     independent of what's being said.
   - *Fused emotion panel* appears only if the pipeline computed a
     combined score, hidden otherwise.
   - *People panel* lists everyone identified in the video with a
     confidence score; *On screen now* shows who's actually visible at
     this exact instant, color-matched to their bounding box.
   - *Also appears in* (sidebar) lists, for each person in this video,
     every other video `global_identity.py` linked them to -- hidden
     entirely if nothing was linked (see "Post-processing" above and
     "Emotion statistics" below).
   - *Emotion insights* (sidebar) shows three fixed statistics for the
     current video -- video/text agreement, dominant-emotion
     distribution, and per-person valence/arousal averages -- see
     "Emotion statistics" below for what each one means.
3. **Ask a question** -- the box at the top skips manual scrubbing
   entirely. Type something like *"find the moments of highest anger"*
   or *"where do video and text emotion disagree?"* and hit **Ask**.
   A few things worth knowing:
   - It genuinely takes time -- anywhere from a few seconds to several
     minutes, since it's an agent iterating on real SQL against a
     shared, slow model, not a canned lookup (see "Natural-language
     query agent" below). There's no progress bar yet, so don't
     resubmit while it says "Thinking...".
   - Results come back as a clickable list -- click any row and the
     player jumps straight to that clip, automatically switching the
     sidebar/overlays to show *only* what's relevant to your question
     (e.g. asking about anger hides panels that question didn't ask
     about).
   - **"Reset view"** clears the query and goes back to showing
     everything, for normal browsing.

That's the whole loop: browse normally by picking a video and
scrubbing, or let the query agent jump you straight to the moments you
actually care about.

**Setup:**

1. Put the actual video file(s) in the same directory as the `.xmi`
   you're importing, named exactly as the CAS's own filename (e.g. if
   the CAS says `filename = 'first2.mp4'`, the file must sit right next
   to it as `cas/first2.mp4`). The database only stores metadata, never
   the video bytes.
2. Run the parser (`python main.py`) so there's data to show -- as of
   the post-processing step in `duui_parser/media.py`, this also places
   the video where the webapp expects it (`DUUI_VIDEO_DIR` in `.env`,
   defaults to `cas/`), so with the default config there's normally
   nothing further to do here: source and served directory are the
   same directory, and the copy is skipped when it would be a no-op.
   Only relevant if you point `DUUI_VIDEO_DIR` somewhere else (or are
   using Docker -- see "Docker architecture" below, where the importer
   and webapp containers deliberately use *different* directories).
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

## Emotion statistics

Two extra sidebar panels surface data the webapp doesn't otherwise
show, both backed by fixed SQL in `webapp/server.py` -- deliberately
**not** routed through the NL->SQL query agent, so they're fast,
deterministic, and available even without `DUUI_QUERY_API_KEY`
configured:

- **`GET /api/persons/global`** ("Also appears in" panel): every
  `global_persons` cluster with 2+ members, i.e. cross-video person
  identity (see "Post-processing" above) made visible in the UI rather
  than only queryable. A person with no cross-video match doesn't
  appear -- most persons, in practice, since it depends on the same
  person genuinely recurring across your imported videos.
- **`GET /api/stats/{video_id}`** ("Emotion insights" panel), three
  fixed analyses per video:
  1. *Video vs. text agreement* -- of the sentences with both a text
     and a video emotion reading, what percentage agree on valence
     sign (both positive or both negative)? A single summary number.
     Uses valence sign rather than comparing `dominant_label` strings
     across modalities directly -- see `schema_context.py`'s
     "Cross-modality label comparison" note for why that would be
     misleading.
  2. *Dominant-emotion distribution* -- how often each `dominant_label`
     occurred, per modality, top 4 shown per modality.
  3. *Average valence/arousal by person* -- per modality, so you can
     see e.g. "this person reads calmer on video than their words
     suggest" at a glance.

**Computed on demand, not written back to the database**: both
endpoints run their SQL fresh on every request rather than caching a
result in a new table. This was a deliberate choice for now -- always
correct as new videos get imported, no cache-invalidation logic needed
-- at the cost of recomputing on every page load. If a stats table
ever becomes worth it (a much larger video library, or these stats
feeding something other than this one UI), the natural next step is a
small `video_stats`-style table these queries write into once, either
as a further step in `PARSE_STEPS` or the query agent -- happy to add
that when there's a concrete second consumer.

## How the webapp knows which DB data belongs to which video

Two keys, one per hop -- worth being explicit about, since it's what
keeps the importer and the webapp in sync without them sharing
anything but the database and the video store:

1. **`video_id` links all DB rows to one video.** The CAS's own
   `MultimediaElement` becomes exactly one row in `videos`, and
   *every* other table carries a `video_id` foreign key back to it
   (`segments`, `linguistic_tokens`, `persons`, `presences`,
   `face_detections`, `person_detections`, `base_emotions`,
   `fused_emotions`, ...). So "all the data for this video" is just
   `WHERE video_id = X` -- which is precisely what
   `GET /api/videos/{video_id}/data` does.
2. **`videos.filename` links that DB row to the file on disk.** The
   filename is read out of the CAS itself and stored on the `videos`
   row; the importer copies the video into the video store under that
   exact name (`duui_parser/media.py`), and the webapp serves it from
   `<DUUI_VIDEO_DIR>/<filename>` (`GET /media/{filename}`). Nothing
   else is negotiated between the two containers -- same store, same
   filename.

So the frontend flow is: `GET /api/videos` (returns `video_id` +
`filename` + `video_file_available`) → pick one → `GET
/api/videos/{video_id}/data` for everything in Postgres, and
`/media/{filename}` for the video bytes, played back in sync.

Because point 2 is a filename convention rather than an enforced
constraint, `GET /api/videos` **checks the file's existence live** on
every call and reports it as `video_file_available` -- so a DB row
whose video never arrived (import ran before the file was placed, or
it was deleted) shows up as unavailable in the dropdown instead of
failing mysteriously at playback. The database never stores video
bytes.

## Docker architecture

If you're running the stack via `docker compose` (see `docker-compose.yml`)
rather than a local venv, this is the three-container shape and how a
CAS goes from "file on disk" to "playable in the browser":

```
 pipeline output          importer (one-off)              webapp (long-running)
 cas/x.xmi + cas/x.mp4 ─▶  1. parse x.xmi -> Postgres  ┐
  (dropped on host,        2. copy x.mp4 -> video_media├─▶ reads Postgres +
   ./cas bind mount)                                    │   video_media (ro)
                                                          ┘
```

1. **What comes out of the pipeline**: a CAS (`.xmi`) plus its source
   video, as a pair, same base handling as the non-Docker path in
   step 4 above -- both get dropped into `cas/` on the host.
2. **The importer** is a one-off container, not a long-running
   service (`docker compose run --rm importer ...`, excluded from
   `docker compose up` by the `import` profile) -- it parses the CAS
   into Postgres *and* copies the matching video file into the
   `video_media` named volume (see `duui_parser/media.py`), so nothing
   manual has to happen afterwards to make the two line up. It's
   deliberately **not** folded into the webapp container: keeping it
   separate means `webapp/Dockerfile` never needs `dkpro-cassis`/lxml
   (only `webapp/requirements.txt`, kept lean since `webapp/server.py`
   never parses CAS files, only reads Postgres), and an import can be
   scripted/re-run independently of the running webapp.
3. **The webapp** mounts `video_media` **read-only** and never touches
   `./cas` directly -- it only ever knows about a video because the
   importer already placed it there under the exact `videos.filename`
   value, which is the join key between "a row in Postgres" and "a
   file it can stream". `GET /api/videos` reports `video_file_available`
   per video by checking this live, so a DB row whose video hasn't
   been placed yet (or was removed) is visible as such rather than
   just 404ing when you try to play it.
4. Point 4's `webapp` capabilities (transcript/emotions/bounding boxes,
   the NL query agent, cross-video person view, emotion stats -- see
   "Web viewer" and "Emotion statistics" below) are unchanged by this
   -- this section is purely about how the two containers stay in sync
   on what data exists.

**What to mount** (already wired up in `docker-compose.yml`):
- `./cas:/app/cas` (importer only, read-write) -- the pipeline's drop
  zone: both the `.xmi` file you're importing and its companion video,
  same filename the CAS itself carries.
- `./typesystems:/app/typesystems:ro` (importer only) -- the three
  typesystem XML files from step 3 above.
- `video_media` (named volume) -- read-write on `importer`, read-only
  on `webapp`. Never bind-mounted to the host directly; it only ever
  gets content via the importer's copy step.

**Env vars the importer container needs** (already set by
`docker-compose.yml`'s `importer.environment` block -- only relevant
if you're running the built image directly instead of through compose):
- `DUUI_DB_HOST=db` -- the Postgres service's name on the compose
  network, **not** `localhost` (that only works when running `main.py`
  on the host against the container's exposed port 5432).
- `DUUI_DB_NAME`, `DUUI_DB_USER`, `DUUI_DB_PASSWORD` -- must match the
  `db` service's `POSTGRES_*` values (`duui_bundestag`/`duui`/`duui`).
- `DUUI_VIDEO_DIR=/media` -- where the companion video gets copied to
  (the `video_media` mount point), **not** the `/app/cas` input mount.
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
bottom of this README; re-copying an already-placed video file is a
no-op too (`duui_parser/media.py` checks the destination first).

**If the video wasn't next to the CAS at import time**: the DB import
still succeeds (data is more valuable than nothing), but you'll see a
`[duui_parser] warning: no source video found at ...` in the importer's
logs and `video_file_available: false` from the API for that video.
Placing the file afterwards just needs it copied into the
`video_media` volume under the exact `videos.filename` value, e.g.:
```bash
docker run --rm -v duui_bundestag_pipeline_video_media:/media -v "$(pwd)/cas:/src:ro" alpine \
  cp /src/your_file.mp4 /media/your_file.mp4
```
(adjust the volume name if `docker compose config --volumes` reports a
different project prefix).

**Alternative considered**: folding the import step directly into the
webapp container (e.g. an upload endpoint) instead of a separate
one-off container -- rejected for now to keep the webapp image free of
the CAS-parsing dependency chain and to keep "import a file" scriptable
as a plain CLI invocation, but worth revisiting if imports need to be
triggerable from the browser rather than a terminal with host access.

## Natural-language query agent

The "Ask" bar above the player lets you type a question like *"give me
the video sequences where video emotion and text emotion diverge"*
instead of writing SQL by hand, and get back a clickable list of the
exact clips that answer it. This is a genuine agent, not a canned
query template: it explores the schema, writes real SQL, checks its
own work, and decides which parts of the UI are relevant to show --
all driven by `duui_parser/query_agent/`.

### How a question actually gets answered

```
 "find the moments of highest anger"
              │
              ▼
   ┌───────────────────────────────────────────────────────────┐
   │  agent.py -- tool-use loop, up to 6 iterations              │
   │  (openai SDK, OpenAI-compatible chat-completions endpoint)   │
   └───────────────────────────────────────────────────────────┘
              │                              ▲
              │ 1. model calls run_sql(...)   │ 4. preview: columns,
              ▼                                │    up to 20 rows,
      ┌──────────────────┐                     │    row count, or an
      │  sql_guard.py     │────────────────────┘    error message
      │  validate + run   │  2. reject non-SELECT / DML / multi-statement
      │  read-only,       │  3. execute inside READ ONLY transaction,
      │  row-capped       │     statement_timeout, LIMIT wrapper
      └──────────────────┘
              │
              │ 5. model repeats 1-4 to fix a bad query, then calls
              │    submit_answer(sql, explanation, overlays) once
              ▼
   agent.py re-runs *that exact SQL* itself via sql_guard.py again --
   never trusting rows the model merely claims to have seen -- and
   returns {sql, explanation, overlays, columns, rows, row_count}
```

The three files, each with one job:

1. **`schema_context.py`** is the system prompt: not just `information_schema`
   (which can't tell you that `duration`/`fps` are almost always NULL, that
   `global_persons` is essentially unused in practice, or that comparing
   emotions across modalities means joining through the `segments` row
   whose time window they fall inside). It's cross-checked against three
   sources -- the intended schema doc, what the parser's INSERT statements
   actually write, and a live query against a populated database for real
   label vocabularies -- and includes one fully worked example query for
   cross-modal "divergence" questions, since that pattern is the hardest
   one to get right from column names alone.
2. **`agent.py`** owns the loop and the two tools the model can call:
   `run_sql` (a sandboxed preview -- 20 rows, total count, or an error to
   learn from) to explore and validate candidate queries, and
   `submit_answer` (final SQL + a plain-language explanation + which
   **overlays** the frontend should show) to finish. If the model responds
   with plain text instead of calling a tool, it gets nudged back on track
   rather than the request failing outright. Any API-level failure (bad
   key, rate limit, model timeout) is caught and surfaced as a clean `422`
   with a real message, not a raw `500`.
3. **`sql_guard.py`** is what actually keeps this safe to run against a
   real database, in two independent layers -- because neither alone
   would be trustworthy against a model that might emit something
   unexpected: a syntactic check rejecting anything that isn't a single
   `SELECT`/`WITH ... SELECT` statement (multi-statement input and any
   DML/DDL keyword -- `INSERT`, `DROP`, `GRANT`, `COPY`, ... -- are blocked
   before the query ever reaches Postgres), *and* Postgres's own
   `SET TRANSACTION READ ONLY`, enforced by the engine regardless of what
   slipped past the first check. On top of that, every query runs with a
   statement timeout (`DUUI_QUERY_STATEMENT_TIMEOUT_MS`, default 8000ms --
   catches e.g. a missing join condition blowing up into a huge cross
   product) and a hard row cap (`DUUI_QUERY_MAX_ROWS`, default 500, applied
   by wrapping the query in `SELECT * FROM (<query>) AS _sub LIMIT n`).

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
provider/model if needed. Note this particular model is slow: a single
question can take anywhere from a few seconds to several minutes,
depending on how many `run_sql` iterations it needs (multi-step tool use
against a large model, no progress indicator in the UI yet) -- that's
expected, not a hang.

### Use cases (all validated against the real Bundestag sample data)

These are questions we actually ran through the agent end-to-end, not
hypothetical examples -- included to show the range of what "explore
the schema and write real SQL" covers in practice:

- **Cross-modal divergence** -- *"where do video emotion and text
  emotion diverge?"* The motivating use case, and the one worked
  example baked into the system prompt: join `base_emotions` rows from
  the `video` and `text` modalities through the `segments` row whose
  time window contains both, and surface sentences where the two
  disagree. Overlays picked: `transcript`, `video_emotion`,
  `text_emotion`, `bounding_boxes` (not `audio_emotion` or
  `fused_emotion`, since the question never asked about those).
- **Emotional highlights** -- *"find the moments of highest anger in
  the video"*. The agent independently discovered it needed to check
  all three modalities' differing label vocabularies for the same
  emotion (`'Anger'` for video, `'angry'` for audio, `'anger'` for
  text) rather than assuming one shared spelling, unioned them, joined
  to `persons` for display names, and sorted by confidence score --
  entirely without being told the vocabularies differ (that's
  documented in `schema_context.py`, not hardcoded into the query).
- **Speaker-focused** -- *"when is person_1 speaking, and what's their
  tone?"* A `segments` (`kind = 'sentence'`) join to `persons` filtered
  on `clip_label`, giving back every time window that speaker talks.
- **On-screen presence** -- *"who is visible on screen throughout the
  video?"* Reads `presences` (modality `'visible'`), left-joined to
  `persons` so intervals with no resolved identity correctly come back
  labeled `'unidentified'` rather than being silently dropped.
- **Confidence-based** -- *"how confident was the model in the
  Contempt reading at various points?"* Joins `base_emotions` to
  `emotion_scores` for a specific label and ranks by `score` -- useful
  for judging whether a labeled emotion is a strong or borderline read.
- **Intensity ranking** -- *"rank the most emotionally intense
  sentences by valence/arousal magnitude"*. Computes
  `sqrt(valence^2 + arousal^2)` per sentence from the audio-modality
  `base_emotions` row covering it, ranking "how strong," not just
  "which label."
- **Simple aggregates** -- *"how many sentences are in this video?"*
  resolves in a single `run_sql` call with no exploration needed --
  the loop only takes as many iterations as the question actually
  requires.
- **A deliberately malicious probe** -- `DELETE FROM videos WHERE
  video_id = 16126` run directly through `sql_guard.run_read_only`
  (bypassing the agent, to test the guard itself) was correctly
  rejected with `"Query must start with SELECT or WITH."` before ever
  reaching Postgres.

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Covers the two places a silent bug would be worst: `sql_guard.py` (the
NL->SQL agent's queries are untrusted input -- pure validation tests
plus a couple that actually hit a real DB to prove the `READ ONLY`
transaction itself blocks a write, not just the regex) and the DB
-writing logic in `global_identity.py`/`emotion_fusion.py` (does the
matching/averaging actually produce the right rows), plus
`media.py`'s filesystem logic (copy/idempotency/missing-file handling,
no DB needed). DB-backed tests are auto-**skipped**, not failed, if no
Postgres is reachable via `DUUI_DB_*`/`.env` -- point them at a local
Postgres or `docker compose up -d db` with `schema/schema.sql` applied
to run the full suite. Every DB-backed test runs on one connection and
rolls it back at teardown (see `tests/conftest.py`), so nothing needs
manual cleanup and the suite is safe to run against a real populated
database without touching its data.

CI (`.github/workflows/ci.yml`) runs the full suite against a fresh
`pgvector/pgvector:pg16` service container on every push/PR, plus a
separate job that just builds both Docker images (catches a broken
`Dockerfile`/`requirements.txt` even if nothing else regressed).

## Operating this (health checks, backups)

- **Liveness**: `GET /healthz` on the webapp does a real `SELECT 1`
  against Postgres, not just "the process is up" -- what
  `docker-compose.yml`'s `webapp` healthcheck polls, and what any
  reverse proxy / orchestrator in front of this should point at too.
- **Backups**: nothing here does this for you yet -- the `db_data`
  volume is the only thing that isn't trivially reproducible (videos
  live outside the DB entirely; CAS files are the pipeline's own
  output, presumably kept upstream). A plain
  `docker compose exec db pg_dump -U duui duui_bundestag > backup.sql`
  (and `psql ... < backup.sql` on a fresh `db_data` volume to restore)
  is enough to start with; automate it (cron, or a `pg_dump` sidecar
  container) before this holds data you can't regenerate by
  re-importing.
- **What was deliberately left out for this (internal) deployment**:
  no auth in front of the webapp, no TLS, no rate limiting on
  `/api/ask`. That's a fine tradeoff on a trusted internal network;
  revisit it (auth + a reverse proxy terminating TLS, at minimum) the
  moment this becomes reachable from anywhere less trusted than that,
  since it currently gives anyone who can reach it full read access to
  every imported video's data, including cross-video identity links.

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

A second addition: HNSW indexes on `face_embeddings.embedding` /
`voice_embeddings.embedding` (`vector_cosine_ops`) -- the schema doc
always described these as pgvector-HNSW-indexed, but the index
statements themselves were missing until the cross-video person
linking step (see above) actually needed them for real nearest
-neighbor lookups. A few plain B-tree indexes were added alongside
them for the join patterns the post-processing steps and the query
agent use most (`base_emotions(video_id, modality)`,
`segments(video_id, kind)`, `face_embeddings(person_id)`,
`voice_embeddings(person_id)`). If your database predates this,
re-running `psql -d duui_bundestag -f schema/schema.sql` picks up the
new indexes without touching existing data -- the `CREATE TABLE`
statements will each print a harmless "relation already exists" error
and get skipped, since only the index statements at the end use
`CREATE INDEX IF NOT EXISTS`; nothing gets dropped or overwritten.
