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

> **Longer term**: mounting is the pull model. The push model — an
> upload endpoint or a watched drop directory hands each CAS+video to
> the importer — is an entry point in front of the existing CLI job,
> not a rewrite. Mounting is the right amount of machinery until then.

### And where do the extracted videos end up?

**The importer handles this for you.** After it writes a CAS's rows into
Postgres, it copies that CAS's video into the *video store* under
exactly the filename recorded in the database. The viewer mounts the
same store read-only. That's the whole mechanism — you never place,
rename or move a video by hand.

By default the store is a Docker-managed named volume (`video_media`),
so there's nothing to set up. To have it as a normal folder you can
browse and back up, point it at a host path instead:

```bash
DUUI_VIDEO_STORE=/absolute/path/to/duui-videos
```

Either way both containers must use the **same** store — with compose
that's automatic.

---

## Quickstart

Requires Docker (with Compose v2). Nothing else — no Python, no
Postgres, no **ffmpeg** on your machine (see "Prerequisites").

```bash
docker compose up -d
```

That's it — open **http://localhost:8010** and the shipped sample video
is playing. The first run builds the images (~1-2 min), then starts the
database, **runs the import**, and starts the viewer.

To use your own data instead of the sample, set the input folder once
first (you do not move your files — see the section above):

```bash
cp .env.example .env && $EDITOR .env      # set DUUI_INPUT_HOST_DIR
docker compose up -d
```

Verify at any time:

```bash
docker compose ps
```

You should see `db` and `webapp` as `(healthy)`, plus `init-import` as
`Exited (0)` — that one is the import job, which is *supposed* to exit
once it's finished.

> **Why the import runs as part of `up`:** starting only the database
> and the viewer left the database empty, so the app came up with an
> empty dropdown and a blank player — indistinguishable from a broken
> deployment. If the database *is* ever empty, the viewer now says so
> explicitly instead of showing a black rectangle.

### Everyday commands

All of these run from this directory (`cd` here first):

```bash
docker compose ps                 # status -- db and webapp should say (healthy)
docker compose logs -f webapp     # follow the viewer's log (or: db)

docker compose stop               # stop, keep containers
docker compose down               # stop and remove containers -- DATA IS KEPT
docker compose down -v            # ...and delete the database + video store too

docker compose build              # rebuild images after changing code
docker compose up -d --build webapp   # rebuild and restart just the viewer
```

Importing more data later never needs a restart — run the job again and
reload the page:

```bash
docker compose run --rm importer
DUUI_INPUT_HOST_DIR=/other/folder docker compose run --rm importer   # different source
```

If port 8010 or 5432 is already in use, set `DUUI_WEBAPP_HOST_PORT` /
`DUUI_DB_HOST_PORT` in `.env` (see "Configuration reference").

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
docker compose run --rm importer                               # everything in the input folder
docker compose run --rm importer /data/input/session1.xmi      # one specific file
docker compose run --rm importer /data/input/sub /data/input/a.xmi   # any mix of dirs and files
```

Paths are interpreted **inside** the container, where your input folder
is mounted at `/data/input` — so they have to be written as container
paths, not as paths on your machine. Relative paths resolve against the
image's working directory (`/app`), not against the input folder, so
prefix them with `/data/input/`.

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

If the import reports **`No .xmi files found`**, the line under it says
which of the three causes it was:

```
No .xmi files found in: /data/input
  - /data/input: directory exists but cannot be read (Permission denied) -- check the mount's permissions
```

- *cannot be read* — SELinux. On openSUSE/Fedora/RHEL the container runs
  as `container_t` and may not read files labelled `user_home_t`, so the
  mount is invisible even to root inside the container. The `z` flag on
  the input mount in `docker-compose.yml` handles this by relabelling
  the folder; if you mount input yourself, add `:ro,z` too.
- *is empty* — `DUUI_INPUT_HOST_DIR` points somewhere that doesn't
  exist. Docker creates the missing path as an empty directory rather
  than failing. Note an exported shell variable overrides `.env`.
- *none named `*.xmi`* — right folder, no CAS in it (the entries it did
  find are listed, so a wrong subfolder is obvious).

### 3. Start the viewer

```bash
docker compose up webapp        # first time: no -d, so you see it finish
docker compose up -d webapp     # later starts
```

**The first run builds the webapp image (~30-60 s).** With `-d` that
happens silently, and if it is interrupted before finishing (Ctrl-C,
closing the terminal, moving on too early) **no container is created at
all** — nothing crashes, nothing reaches the logs, the port just doesn't
respond. That looks exactly like "the app has no data" even when the
database and video store are fine. Hence the foreground run above, and
`docker compose ps` afterwards: if `webapp` is missing from the list
entirely, the start never completed — run it again.

Then open http://localhost:8010 and pick a video from the dropdown. It
lists everything in the database and marks any video whose file is
missing from the store, so a half-finished import is visible rather than
mysterious.

**If the dropdown is empty or the video won't play**, go through these in
order — each one narrows down which hop is broken:

```bash
docker compose ps                    # 1. is webapp present AND healthy?
curl localhost:8010/healthz          # 2. app up, and reaching Postgres?  -> {"status":"ok"}
curl localhost:8010/api/videos       # 3. rows in the DB? video_file_available true?
docker compose logs webapp           # 4. anything actually erroring?
```

- **1 fails / `webapp` missing** → the container was never started. Re-run
  step 3 (this is the most common cause by far).
- **2 fails** → the app is running but can't reach the database. Check
  `docker compose ps` for `db` and `docker compose logs db`.
- **3 returns `[]`** → the database is empty; the import didn't land.
  Re-run step 2 and read its summary line.
- **3 shows `"video_file_available": false`** → the row exists but its
  video never reached the store. See "How does the viewer know which data
  belongs to which video?" below for how to place it without re-importing.

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

(The prefix is the compose project name, which `docker-compose.yml`
pins to `duui-bundestag-stack` rather than deriving from the folder
name. `docker volume ls` shows the full names.)

---

## Prerequisites

**Docker path (recommended)**: Docker with Compose v2. That's it — no
Python, no Postgres, no **ffmpeg**, no system libraries. Nothing here
shells out to an external binary; videos are streamed byte-for-byte to
the browser and never transcoded. (The upstream DUUI pipeline that
*produces* the CAS files does need ffmpeg and GPUs — separate project,
this stack only consumes its output.)

**For running the tests or the importer directly on the host**: Python
3.12, and Postgres 16+ with **pgvector** available.

**Optional NLP enrichment**: needs a spaCy German model (~13 MB). Off by
default — uncomment the two `requirements-nlp.txt` lines in
`importer/Dockerfile`, rebuild, and set
`DUUI_ENABLE_NLP_ENRICHMENT=true`.

---

## Running without compose

Every container has its own build script, and every image builds with
**its own folder** as the context — `db/`, `importer/` and `webapp/`
are self-contained, with no code shared between them:

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
environment. Each container defines the ones it reads:
`importer/duui_parser/config.py` and `webapp/duui_webapp/config.py`.
The few that appear in both (`DUUI_DB_*`, `DUUI_VIDEO_DIR`) are exactly
the two contracts the containers share — the database and the video
store — and compose passes the same values to both services.

**Paths and ports** (read on the host, to build the compose file):

| Variable | Default | What it is |
| :--- | :--- | :--- |
| `DUUI_INPUT_HOST_DIR` | `./importer/sample-input` | **Your** folder of `.xmi` files + videos. Mounted read-only; never modified |
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

Those defaults come from `docker-compose.yml`. Running the code
straight on the host without them set (no `.env`, no exports) falls
back to the placeholders in `config.py` (`your_db` / `your_user`), so
the connection simply fails — which is why the DB-backed tests skip
rather than error when you haven't pointed them anywhere.

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

Each container has its own suite next to its code
(`importer/tests/`, `webapp/tests/`). From the stack root, `pytest`
runs both:

```bash
pip install -r importer/requirements.txt -r webapp/requirements.txt \
            -r requirements-dev.txt
pytest
```

Or one side on its own, needing only that side's requirements:

```bash
cd importer && pytest        # or: cd webapp && pytest
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
│   ├── duui_parser/       the CAS parsers, post-processing, DB layer
│   ├── tests/             pytest suite for the above
│   └── sample-input/      small demo .xmi + video (the default input)
├── webapp/                Dockerfile, build.sh, server.py, static/
│   ├── duui_webapp/       settings, DB layer, NL→SQL agent
│   └── tests/             pytest suite for the above
└── docs/                  schema reference, screenshots
```

Each folder is self-contained — it holds all the code its image needs
and nothing it doesn't, which is why each builds with its own folder as
the Docker context. The importer never imports the viewer's code or
vice versa; they share only the database and the video store, wired up
in `docker-compose.yml`. The price is a little deliberate duplication
(the DB connection helper, the `DUUI_DB_*` / `DUUI_VIDEO_DIR` settings,
the pytest DB fixture) — a handful of lines each, and what lets either
container be built, tested or lifted out of this repo on its own.
