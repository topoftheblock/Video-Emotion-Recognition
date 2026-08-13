# DUUI Bundestag Video-Emotion Stack

Takes the output of the DUUI video-emotion pipeline (UIMA CAS `.xmi`
files plus the videos they describe), loads it into Postgres, and serves
a browser viewer that plays each video with its subtitles, per-modality
emotions and face/person bounding boxes rendered live in sync.

Three containers, each buildable on its own:

| Folder | Container | What it is |
| :--- | :--- | :--- |
| `db/` | `duui-db` | Postgres 16 + pgvector, schema baked in |
| `importer/` | `duui-importer` | **One-off job**: parses `.xmi` → Postgres, and copies the videos where the viewer can find them. Runs, works, exits |
| `webapp/` | `duui-webapp` | The viewer (FastAPI + static frontend). Long-running |

```
YOUR pipeline output folder            duui-importer (one-off)                duui-webapp
(stays exactly where it is)      ┌──▶ 1. parse .xmi ──▶ Postgres ◀───────────── reads DB
  session1.xmi + session1.mp4 ───┤                                                  ▲
  session2.xmi + session2.mp4 ───┘    2. copy .mp4 ──▶ video store ────────────────┘
        mounted READ-ONLY                                (shared)         reads read-only
```

---

## Where do my `.xmi` files and videos have to be?

**Wherever they already are. You do not move or copy anything.**

You point the stack at that folder once, and it gets mounted **read-only**
into the importer, in place:

```bash
cp .env.example .env
# then edit .env:
DUUI_INPUT_HOST_DIR=/absolute/path/to/your/pipeline/output
```

Or without an `.env` file at all, per command:

```bash
DUUI_INPUT_HOST_DIR=/absolute/path/to/output docker compose run --rm importer
```

The only requirement on that folder: **each `.xmi` sits next to the
video file it references.** The CAS records its own video's filename
internally, and the importer looks for that filename in the same
directory as the `.xmi`. So this is fine:

```
/my/pipeline/output/
├── session1.xmi        ← references "session1.mp4"
├── session1.mp4
├── session2.xmi        ← references "session2.mp4"
├── session2.mp4
└── notes.txt           ← ignored
```

Everything else — subfolders, unrelated files, other formats — is
ignored. The folder is never written to.

> **Longer term**: mounting a folder is the pull model. The natural
> evolution is the push model — the backend gets handed each CAS+video
> (an upload endpoint, or a watched drop directory) and imports it
> itself, so nothing has to be mounted at all. The importer is already
> a self-contained job with a plain CLI, so that change is an entry
> point in front of it, not a rewrite. Mounting is the right amount of
> machinery until then.

### And where do the extracted videos end up?

**The importer handles this for you.** After it writes a CAS's rows into
Postgres, it copies that CAS's video into the *video store* under
exactly the filename recorded in the database. The viewer mounts the
same store read-only. That's the whole mechanism — you never place,
rename or move a video by hand.

By default the video store is a Docker-managed named volume
(`video_media`), so there's nothing to set up. If you'd rather have it
as a normal folder you can browse and back up, point it at a host path:

```bash
DUUI_VIDEO_STORE=/absolute/path/to/duui-videos
```

Either way, both the importer and the viewer must use the **same** store
— with compose that's automatic.

---

## Quickstart

Requires Docker (with Compose v2). Nothing else — no Python, no
Postgres, no **ffmpeg** on your machine (see "Prerequisites").

```bash
# 0. optional: point at your own data (otherwise the shipped sample is used)
cp .env.example .env && $EDITOR .env      # set DUUI_INPUT_HOST_DIR

# 1. start the database (first start also creates the schema)
docker compose up -d db

# 2. run the import job -- imports every .xmi in your input folder, then exits
docker compose run --rm importer

# 3. start the viewer
docker compose up -d webapp
```

Open **http://localhost:8010**.

Steps 1 and 3 are one-time. Step 2 is what you re-run whenever your
pipeline produces new files — the viewer picks them up without a restart
(just reload the page).

---

## The three jobs in detail

### 1. Start the database

```bash
docker compose up -d db
```

The schema (`db/schema.sql`) is baked into the image and applied
automatically **the first time** the `db_data` volume is created. Wait
for it to report healthy before importing — compose does this for you
(`depends_on: service_healthy`), so step 2 will simply wait:

```bash
docker compose ps            # STATUS should say (healthy)
```

### 2. Run the import job

```bash
docker compose run --rm importer                    # everything in the input folder
docker compose run --rm importer session1.xmi       # one specific file
docker compose run --rm importer sub/ a.xmi b.xmi   # any mix of dirs and files
```

Paths are interpreted **inside** the container, where your input folder
is mounted at `/data/input` (and that's the working directory default),
so `session1.xmi` means `<your input folder>/session1.xmi`.

What one run does, per `.xmi`:

1. Parses the CAS and writes everything into Postgres in **one
   transaction** (video, persons, segments, transcript tokens,
   detections, all three emotion modalities, embeddings).
2. Runs the post-processing steps (see below).
3. Copies the CAS's video into the video store.

Useful behaviour when importing a whole folder:

- **The typesystem is loaded once per run**, not per file — a folder
  import is much faster than one command per file.
- **One transaction per file.** A malformed `.xmi` is reported and
  skipped; the rest of the batch continues. You get a
  `N imported, M failed` summary, and a non-zero exit code if anything
  failed (so a script or cron job notices).
- **Re-running is safe.** Already-imported files are upserted, not
  duplicated, and an already-copied video is left alone. Re-running a
  folder after adding one new file is the normal way to load it.
- **Non-recursive**: `*.xmi` directly inside the given folder. Pass
  subfolders explicitly if you keep sessions in separate directories.
- `--rm` deletes the finished container. Without it you accumulate
  exited containers; nothing else differs.

### 3. Start the viewer

```bash
docker compose up -d webapp
```

Then open http://localhost:8010 and pick a video from the dropdown. It
lists everything in the database and marks any video whose file is
missing from the store, so a half-finished import is visible rather than
mysterious.

---

## How does the viewer know which data belongs to which video?

Two keys, one per hop:

1. **`video_id` ties all database rows to one video.** The CAS becomes
   exactly one row in `videos`, and every other table carries a
   `video_id` foreign key back to it. "All data for this video" is just
   `WHERE video_id = X`.
2. **`videos.filename` ties that row to the file on disk.** The filename
   comes out of the CAS itself; the importer copies the video into the
   store under that exact name, and the viewer serves it from
   `<video store>/<filename>`.

The database never stores video bytes. Because hop 2 is a filename
convention rather than a database constraint, the viewer **checks the
file's existence on every request** and reports it per video
(`video_file_available`) — so if a video never arrived (import ran before
the file was there, or it was deleted), the dropdown says so instead of
failing at playback.

If that happens, you don't need to re-import: just re-run the import job
for that file, or copy the video into the store yourself:

```bash
# named-volume store (the default)
docker run --rm -v duui-bundestag-stack_video_media:/data/videos \
  -v /my/pipeline/output:/src:ro alpine cp /src/session1.mp4 /data/videos/
```

(Check the exact volume name with `docker compose config --volumes`; the
project prefix follows the folder name.)

---

## Prerequisites

**Docker path (recommended)**: Docker with Compose v2. That's it. No
Python, no Postgres, no **ffmpeg**, no system libraries — the images
bring everything, and nothing in this codebase shells out to an
external binary. Videos are streamed byte-for-byte to the browser and
never transcoded; the browser's own video decoder does the work.

(The upstream DUUI pipeline that *produces* the CAS files does need
ffmpeg and GPUs — that's a separate project. This stack only consumes
its output.)

**For running the tests or the importer directly on the host**: Python
3.12, and Postgres 16+ with **pgvector** available.

**Optional NLP enrichment**: needs a spaCy German model (~13 MB). Off by
default — uncomment the two `requirements-nlp.txt` lines in
`importer/Dockerfile`, rebuild, and set
`DUUI_ENABLE_NLP_ENRICHMENT=true`.

---

## Running without compose

Every container has its own build script. The importer and webapp
images build with the **stack root** as context (they share
`shared/duui_parser/`), which the scripts handle for you:

```bash
./build-all.sh          # all three
./db/build.sh           # or individually
./importer/build.sh
./webapp/build.sh

IMAGE_TAG=v2 ./webapp/build.sh     # custom tag
```

Then wire them up by hand — compose otherwise does exactly this:

```bash
docker network create duui

# 1. database
docker run -d --name duui-db --network duui \
  -e POSTGRES_DB=duui_bundestag -e POSTGRES_USER=duui -e POSTGRES_PASSWORD=duui \
  -v duui_db_data:/var/lib/postgresql/data \
  -p 5432:5432 \
  duui-db:latest

# 2. import job (one-off; add paths as arguments to narrow it down)
docker run --rm --network duui \
  -e DUUI_DB_HOST=duui-db -e DUUI_DB_NAME=duui_bundestag \
  -e DUUI_DB_USER=duui -e DUUI_DB_PASSWORD=duui \
  -v /my/pipeline/output:/data/input:ro \
  -v duui_videos:/data/videos \
  duui-importer:latest

# 3. viewer
docker run -d --name duui-webapp --network duui \
  -e DUUI_DB_HOST=duui-db -e DUUI_DB_NAME=duui_bundestag \
  -e DUUI_DB_USER=duui -e DUUI_DB_PASSWORD=duui \
  -v duui_videos:/data/videos:ro \
  -p 8010:8000 \
  duui-webapp:latest
```

The importer and the viewer must share the same video volume
(`duui_videos` here) and reach the same database. Nothing else is
shared between them.

---

## Configuration reference

Everything is an environment variable, read from `.env` or the real
environment. `shared/duui_parser/config.py` is where they're all
defined.

**Paths and ports** (read on the host, to build the compose file):

| Variable | Default | What it is |
| :--- | :--- | :--- |
| `DUUI_INPUT_HOST_DIR` | `./sample-input` | **Your** folder of `.xmi` files + videos. Mounted read-only; never modified |
| `DUUI_VIDEO_STORE` | `video_media` | Where imported videos live. Plain name = Docker volume; host path = bind mount |
| `DUUI_WEBAPP_HOST_PORT` | `8010` | Host port for the viewer (container always listens on 8000) |
| `DUUI_DB_HOST_PORT` | `5432` | Host port for Postgres. Change if you run one locally |

**Container-side paths** (already set by compose; only relevant when
running the images by hand):

| Variable | Default in image | What it is |
| :--- | :--- | :--- |
| `DUUI_INPUT_DIR` | `/data/input` | Directory the importer reads |
| `DUUI_VIDEO_DIR` | `/data/videos` | Directory the importer writes videos to / the viewer serves from |
| `DUUI_XMI_FILE` | *(unset)* | If set, a no-argument import does just this one file |
| `DUUI_TS_IDENTITY_EMOTION`<br>`DUUI_TS_MULTIMODAL_IDENTITY`<br>`DUUI_TS_EMOTION` | `typesystems/*.xml` | Only if your typesystem filenames differ |

**Database**:

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DUUI_DB_NAME` | `duui_bundestag` | |
| `DUUI_DB_USER` | `duui` | |
| `DUUI_DB_PASSWORD` | `duui` | Change it for anything beyond a local/internal deployment |
| `DUUI_DB_HOST` | `localhost` | Compose sets `db` (the service name) inside containers |

**Natural-language "Ask" panel** (optional — empty key = feature off,
everything else unaffected):

| Variable | Default |
| :--- | :--- |
| `DUUI_QUERY_API_KEY` | *(empty)* |
| `DUUI_QUERY_BASE_URL` | `https://lehre.llm.texttechnologylab.org/api` |
| `DUUI_QUERY_MODEL` | `gondor.qwen3-vl:32b` |
| `DUUI_QUERY_MAX_ROWS` | `500` |
| `DUUI_QUERY_STATEMENT_TIMEOUT_MS` | `8000` |
| `DUUI_QUERY_MAX_TOOL_ITERATIONS` | `6` |

**Post-processing** (all run during import):

| Variable | Default | What it does |
| :--- | :--- | :--- |
| `DUUI_ENABLE_GLOBAL_PERSON_LINKING` | `true` | Links the same person across videos via pgvector similarity on face/voice embeddings |
| `DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD` | `0.30` | Cosine distance; lower = stricter |
| `DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD` | `0.35` | |
| `DUUI_ENABLE_EMOTION_FUSION` | `true` | One fused emotion row per sentence, averaged across available modalities |
| `DUUI_ENABLE_NLP_ENRICHMENT` | `false` | spaCy POS/NER backfill (needs the extra build step) |
| `DUUI_SPACY_MODEL` | `de_core_news_sm` | |

---

## What the viewer shows

- **Video with overlays**: subtitles reconstructed from the transcript
  tokens, a text-emotion badge, and face/person bounding boxes labelled
  with that frame's video-modality emotion.
- **Voice panel**: the audio-modality emotion at the current instant
  plus valence/arousal bars (tone of voice, independent of the words).
- **Fused emotion panel**: the combined multimodal reading.
- **People / On screen now**: who was identified in the video, and who
  is visible at this exact frame, colour-matched to their box.
- **Also appears in**: for each person, other videos they were linked
  to across the corpus (only when such a link exists).
- **Emotion insights**: three fixed statistics — video-vs-text
  agreement, dominant-emotion distribution per modality, and average
  valence/arousal per person. Computed on request in plain SQL (no
  materialised views, no cache).
- **Ask panel** (if configured): a natural-language question is turned
  into SQL by an LLM agent, run read-only, and returned as clickable
  clips that jump the player to that moment — with only the overlays
  relevant to the question shown. Expect seconds to minutes per
  question; it iterates on real SQL.

---

## Post-processing during import

Three things are computed by the importer rather than read from the CAS,
because the CAS doesn't contain them:

1. **Cross-video person identity** — each new person's face/voice
   embedding centroid is compared (pgvector cosine distance) against
   every already-imported video's people; a close enough match links
   both to one global person. This is a **similarity heuristic, not
   verified identity** — tune the thresholds against your own data
   before relying on it.
2. **Emotion fusion** — per sentence, valence/arousal are averaged
   within each modality and then across modalities into one
   `fused_emotions` row.
3. **NLP enrichment** (opt-in) — spaCy POS/NER tags backfilled onto the
   transcript tokens, which the CAS leaves empty.

Each can be switched off independently (see the table above).

---

## Operating it

- **Health**: `GET /healthz` on the viewer runs a real query against
  Postgres, so it fails if the database is unreachable rather than just
  reporting "process alive". Both containers have compose healthchecks.
- **Logs**: `docker compose logs -f webapp` / `db`.
- **Backups**: the `db_data` volume is the only thing not trivially
  reproducible (videos can be re-imported; CAS files live in your
  pipeline output). Nothing automates this yet:
  ```bash
  docker compose exec db pg_dump -U duui duui_bundestag > backup.sql
  # restore into a fresh volume:
  docker compose exec -T db psql -U duui -d duui_bundestag < backup.sql
  ```
- **Upgrading the schema on an existing database**: `db/schema.sql` only
  runs automatically on a *fresh* volume. To apply it to a database that
  already has data (it is written to be safe to re-run — every index is
  `IF NOT EXISTS`, and `CREATE TABLE` errors for existing tables are
  harmless and skipped):
  ```bash
  docker compose exec -T db psql -U duui -d duui_bundestag < db/schema.sql
  ```
- **Deliberately not included**: no authentication, no TLS, no rate
  limiting on the Ask panel. That is a reasonable trade-off on a trusted
  internal network, and a problem anywhere else — anyone who can reach
  the port gets full read access to every imported video, its transcript
  and its cross-video identity links. Put auth and a TLS-terminating
  reverse proxy in front before exposing this more widely.
- **Privacy**: this stores biometric data (face and voice embeddings) of
  identifiable people and links them across recordings. Under GDPR that
  is special-category data (Art. 9) — make sure the legal basis,
  retention and deletion story is settled before running it on real
  recordings at scale.

---

## Tests

```bash
pip install -r importer/requirements.txt -r requirements-dev.txt
pytest
```

Covers the read-only SQL guard the Ask panel's generated queries pass
through (including that the `READ ONLY` transaction itself blocks
writes, not just the keyword check), the cross-video linking and emotion
fusion logic against a real database, the video-placement logic, and
batch path resolution.

Database-backed tests are **skipped**, not failed, when no Postgres is
reachable, so the suite runs anywhere. To run them fully, start the db
container and point the tests at it:

```bash
docker compose up -d db
DUUI_DB_HOST=localhost DUUI_DB_USER=duui DUUI_DB_PASSWORD=duui \
  DUUI_DB_NAME=duui_bundestag pytest
```

Each test runs in one transaction that is rolled back afterwards, so the
suite is safe against a populated database and needs no cleanup.

---

## Layout

```
.
├── docker-compose.yml     all three services, for convenience
├── build-all.sh           builds all three images
├── .env.example           every setting, with defaults
├── db/                    Dockerfile, build.sh, schema.sql
├── importer/              Dockerfile, build.sh, main.py, typesystems/
├── webapp/                Dockerfile, build.sh, server.py, static/
├── shared/duui_parser/    application code used by importer AND webapp
├── tests/                 pytest suite
├── sample-input/          small demo .xmi + video (the default input)
└── docs/                  schema reference, screenshots
```

`shared/duui_parser/` is the actual application: the CAS parsers, the
post-processing steps, the database layer and the NL→SQL agent. Both
images copy it in, which is why they build from the stack root.
