# DUUI Bundestag Video-Emotion Stack

Takes the output of the DUUI video-emotion pipeline (UIMA CAS `.xmi`
files plus the videos they describe), loads it into Postgres, and serves
a browser viewer that plays each video with its subtitles, per-modality
emotions and face/person bounding boxes rendered live in sync.

Three containers, each buildable on its own:

| Folder | Container | What it is |
| :--- | :--- | :--- |
| `db/` | `duui-db` | Postgres 16 + pgvector, schema baked in |
| `duui-video-emotion-cas-to-postgres/` | `duui-video-emotion-cas-to-postgres` | **One-off job**: parses `.xmi` → Postgres, and copies the videos where the viewer can find them. Runs, works, exits |
| `duui-video-emotion-visualization-webapp/` | `duui-video-emotion-visualization-webapp` | The viewer (FastAPI + static frontend). Long-running |

```
YOUR pipeline output folder      duui-video-emotion-cas-to-postgres    ...-visualization-webapp
(stays exactly where it is)      ┌──▶ 1. parse .xmi ──▶ Postgres ◀───────────── reads DB
  session1.xmi + session1.mp4 ───┤                                                  ▲
  session2.xmi + session2.mp4 ───┘    2. copy .mp4 ──▶ video store ────────────────┘
        mounted READ-ONLY                                (shared)         reads read-only
```

Both application folders use the same layout: `src/` is the source root
(it goes on the path, it is not a package), with `tests/` beside it.

---

## Where do my `.xmi` files and videos have to be?

**Wherever they already are. You do not move or copy anything.**

You point the stack at two folders once — one holding the `.xmi`
files, one holding the videos — and both get mounted **read-only**
into the importer, in place:

```bash
cp .env.example .env
# then edit .env:
DUUI_INPUT_XMI_DIR=/absolute/path/to/your/xmi
DUUI_INPUT_VIDEO_DIR=/absolute/path/to/your/videos
```

Or without an `.env` file at all, per command:

```bash
DUUI_INPUT_XMI_DIR=/path/to/xmi DUUI_INPUT_VIDEO_DIR=/path/to/videos \
  docker compose run --rm importer
```

**If your `.xmi` files and videos sit side by side — the common case —
set only the first.** `DUUI_INPUT_VIDEO_DIR` follows
`DUUI_INPUT_XMI_DIR` when it isn't set, so one line is enough:

```bash
DUUI_INPUT_XMI_DIR=/my/pipeline/output      # videos looked for here too
```

Only when **neither** is set does the shipped demo pair apply — a
custom `.xmi` folder never silently sends the video lookup back to the
sample data.

The pairing never depends on the layout: the CAS records its own
video's filename internally, and the importer looks for exactly that
filename in `DUUI_INPUT_VIDEO_DIR`. So both of these work:

```
side by side                      kept apart
/my/pipeline/output/              /my/xmi/            /my/videos/
├── session1.xmi ← "session1.mp4" ├── session1.xmi    ├── session1.mp4
├── session1.mp4                  └── session2.xmi    └── session2.mp4
├── session2.xmi
├── session2.mp4
└── notes.txt   ← ignored
```

Everything else — subfolders, unrelated files, other formats — is
ignored. Neither folder is ever written to.

### What if I only have the `.xmi`?

**Then you need nothing else.** DUUI pipelines carry the video itself
inside the CAS, base64-encoded in a `video/*` sofa (normally
`_InitialView` — set `DUUI_VIDEO_VIEW` if your pipeline routes it to a
different view). When no file named `videos.filename` is found in
`DUUI_INPUT_VIDEO_DIR`, the importer decodes that sofa and writes the
video straight into the video store:

```
[duui_parser] warning: no source video file at /data/input/videos/session1.mp4
[duui_parser] extracted video from CAS sofa '_InitialView' (video/mp4, 25885815 bytes) -> /data/videos/session1.mp4
```

The result is byte-identical to the original file, so a CAS exported
with its sofa intact is fully self-sufficient — `DUUI_INPUT_VIDEO_DIR`
can be left at its default. A companion file on disk is still
preferred when present, purely because copying is cheaper than
decoding tens of megabytes.

`DUUI_VIDEO_VIEW` only has to be set when the CAS holds **several**
video sofas and the right one isn't `_InitialView` — with a single
video sofa it is found either way, and a name that matches no view
falls back to whichever sofa is labelled `video/*` (with a warning, so
a typo is visible). Pointing it at an audio or text view is refused
rather than writing an unplayable file.

If a CAS has *neither* (its video sofa was stripped and no file is
around), the import still completes — only playback is affected, and
the viewer says so per video instead of showing a black frame.

> **Longer term**: mounting is the pull model. The push model — an
> upload endpoint or a watched drop directory hands each CAS+video to
> the importer — is an entry point in front of the existing CLI job,
> not a rewrite. Mounting is the right amount of machinery until then.

### And where do the extracted videos end up?

**The importer handles this for you.** After it writes a CAS's rows into
Postgres, it puts that CAS's video into the *video store* under exactly
the filename recorded in the database — copying the companion file if
there is one, otherwise decoding the copy embedded in the CAS (see
above). The viewer mounts the same store read-only. That's the whole
mechanism — you never place, rename or move a video by hand.

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

To use your own data instead of the sample, set the input folders once
first (you do not move your files — see the section above):

```bash
cp .env.example .env && $EDITOR .env      # set DUUI_INPUT_XMI_DIR
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
# different source:
DUUI_INPUT_XMI_DIR=/other/xmi DUUI_INPUT_VIDEO_DIR=/other/videos \
  docker compose run --rm importer
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
docker compose run --rm importer                                   # everything in the .xmi folder
docker compose run --rm importer /data/input/xmi/session1.xmi      # one specific file
docker compose run --rm importer /data/input/xmi/sub /data/input/xmi/a.xmi   # any mix of dirs and files
```

Paths are interpreted **inside** the container, where your `.xmi`
folder is mounted at `/data/input/xmi` (and your video folder at
`/data/input/videos`) — so they have to be written as container paths,
not as paths on your machine. Relative paths resolve against the
image's working directory (`/app`), not against the input folder, so
prefix them with `/data/input/xmi/`.

What one run does, per `.xmi`:

1. Parses the CAS and writes everything into Postgres in **one
   transaction** (video, persons, segments, transcript tokens,
   detections, all three emotion modalities, embeddings).
2. Runs the post-processing steps (see below).
3. Puts the CAS's video into the video store — the companion file if
   one exists, otherwise the video embedded in the CAS itself.

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
No .xmi files found in: /data/input/xmi
  - /data/input/xmi: directory exists but cannot be read (Permission denied) -- check the mount's permissions
```

- *cannot be read* — SELinux. On openSUSE/Fedora/RHEL the container runs
  as `container_t` and may not read files labelled `user_home_t`, so the
  mount is invisible even to root inside the container. The `z` flag on
  the input mount in `docker-compose.yml` handles this by relabelling
  the folder; if you mount input yourself, add `:ro,z` too.
- *is empty* — `DUUI_INPUT_XMI_DIR` points somewhere that doesn't
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

---

## Running without compose

Every image builds with **its own folder** as the context — `db/`,
`duui-video-emotion-cas-to-postgres/` and
`duui-video-emotion-visualization-webapp/` are self-contained, with no
code shared between them:

```bash
docker build -t duui-db db/
docker build -t duui-video-emotion-cas-to-postgres duui-video-emotion-cas-to-postgres/
docker build -t duui-video-emotion-visualization-webapp duui-video-emotion-visualization-webapp/

docker build -t duui-video-emotion-visualization-webapp:v2 duui-video-emotion-visualization-webapp/   # custom tag
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
  -v /my/xmi:/data/input/xmi:ro \
  -v /my/videos:/data/input/videos:ro \
  -v duui_videos:/data/videos \
  duui-video-emotion-cas-to-postgres:latest

# 3. viewer
docker run -d --name duui-webapp --network duui \
  -e DUUI_DB_HOST=duui-db -e DUUI_DB_NAME=duui_bundestag \
  -e DUUI_DB_USER=duui -e DUUI_DB_PASSWORD=duui \
  -v duui_videos:/data/videos:ro \
  -p 8010:8000 \
  duui-video-emotion-visualization-webapp:latest
```

The importer and the viewer must share the same video volume
(`duui_videos` here) and reach the same database. Nothing else is
shared between them.

---

## Configuration reference

Everything is an environment variable, read from `.env` or the real
environment. Each container defines the ones it reads:
`duui-video-emotion-cas-to-postgres/src/main/config.py` and
`duui-video-emotion-visualization-webapp/src/backend/config.py`.
The few that appear in both (`DUUI_DB_*`, `DUUI_VIDEO_DIR`) are exactly
the two contracts the containers share — the database and the video
store — and compose passes the same values to both services.

**Paths and ports** (read on the host, to build the compose file):

| Variable | Default | What it is |
| :--- | :--- | :--- |
| `DUUI_INPUT_XMI_DIR` | `./duui-video-emotion-cas-to-postgres/src/resources/sample-input` | **Your** folder of `.xmi` files. Mounted read-only; never modified |
| `DUUI_INPUT_VIDEO_DIR` | `DUUI_INPUT_XMI_DIR` (which itself defaults to the sample folder) | **Your** folder of the videos those `.xmi` files reference. Leave unset when they sit next to the `.xmi` files |
| `DUUI_VIDEO_STORE` | `video_media` | Where imported videos live. Plain name = Docker volume; host path = bind mount |
| `DUUI_WEBAPP_HOST_PORT` | `8010` | Host port for the viewer (container always listens on 8000) |
| `DUUI_DB_HOST_PORT` | `5432` | Host port for Postgres. Change if you run one locally |

**Container-side paths** (already set by compose; only relevant when
running the images by hand):

| Variable | Default in image | What it is |
| :--- | :--- | :--- |
| `DUUI_INPUT_XMI_DIR` | `/data/input/xmi` | Directory the importer reads `.xmi` files from |
| `DUUI_INPUT_VIDEO_DIR` | `/data/input/videos` | Directory the importer looks for source videos in |
| `DUUI_VIDEO_DIR` | `/data/videos` | Directory the importer writes videos to / the viewer serves from |
| `DUUI_XMI_FILE` | *(unset)* | If set, a no-argument import does just this one file |
| `DUUI_VIDEO_VIEW` | `_InitialView` | CAS view holding the video, used when it has to be recovered from the CAS rather than a file |
| `DUUI_TS_IDENTITY_EMOTION`<br>`DUUI_TS_MULTIMODAL_IDENTITY`<br>`DUUI_TS_EMOTION` | `src/resources/typesystems/*.xml` | Only if your typesystem filenames differ |

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

**Post-processing** (runs during import):

| Variable | Default | What it does |
| :--- | :--- | :--- |
| `DUUI_ENABLE_GLOBAL_PERSON_LINKING` | `true` | Links the same person across videos via pgvector similarity on face/voice embeddings |
| `DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD` | `0.30` | Cosine distance; lower = stricter |
| `DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD` | `0.35` | |

---

## What the viewer shows

- **Video with overlays**: subtitles reconstructed from the transcript
  tokens, a text-emotion badge, and face/person bounding boxes labelled
  with that frame's video-modality emotion.
- **Voice panel**: the audio-modality emotion at the current instant
  plus valence/arousal bars (tone of voice, independent of the words).
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

One thing is computed by the importer rather than read from the CAS,
because the CAS doesn't contain it:

1. **Cross-video person identity** — each new person's face/voice
   embedding centroid is compared (pgvector cosine distance) against
   every already-imported video's people; a close enough match links
   both to one global person. This is a **similarity heuristic, not
   verified identity** — tune the thresholds against your own data
   before relying on it.

It can be switched off (see the table above).

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
(`duui-video-emotion-cas-to-postgres/tests/`,
`duui-video-emotion-visualization-webapp/tests/`). From the stack root,
`pytest` runs both:

```bash
pip install -r duui-video-emotion-cas-to-postgres/requirements.txt \
            -r duui-video-emotion-visualization-webapp/requirements.txt \
            -r requirements-dev.txt
pytest
```

Or one side on its own, needing only that side's requirements:

```bash
cd duui-video-emotion-cas-to-postgres && pytest
```
```bash
cd duui-video-emotion-visualization-webapp && pytest
```

Covers the read-only SQL guard the Ask panel's generated queries pass
through (including that the `READ ONLY` transaction itself blocks
writes, not just the keyword check), the viewer's HTTP surface via
`TestClient` (route wiring, the frontend being served, the `/media`
mount), subtitle assembly from token timings, the agent-result →
playable-clip conversion, the cross-video linking logic against a real
database, the video-placement logic, and batch path resolution.

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
├── .env.example           every setting, with defaults
├── db/                    Dockerfile, schema.sql
├── duui-video-emotion-cas-to-postgres/
│                          Dockerfile, requirements.txt
│   ├── src/               source root (on the path, not a package)
│   │   ├── main/          the CAS parsers, post-processing, DB layer,
│   │   │                  and __main__.py (the `python -m main` entry)
│   │   └── resources/     typesystems/ + sample-input/ (demo .xmi
│   │                      + video, the default input)
│   └── tests/             pytest suite for the above
├── duui-video-emotion-visualization-webapp/
│                          Dockerfile, requirements.txt
│   ├── src/               source root (on the path, not a package)
│   │   ├── backend/       settings, DB layer, queries/, routes/, the
│   │   │                  NL→SQL agent, and __main__.py (the
│   │   │                  `python -m backend` entry)
│   │   └── frontend/      index.html + css/ + js/ (ES modules, no
│   │                      build step), served as static files
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

The two packages are named differently (`main` and `backend`) on
purpose: the stack root's `pyproject.toml` puts both source roots on
one path so `pytest` can run the suites together, and a shared package
name would make one shadow the other.
