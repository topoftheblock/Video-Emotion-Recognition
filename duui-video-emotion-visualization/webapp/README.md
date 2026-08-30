# webapp

The interface: a FastAPI backend serving a static frontend.

It reads the database and the video store, and plays a video with its
annotations laid over it — transcript subtitles, per-modality emotion readings,
bounding boxes for the people on screen, and where else in the corpus each of
them appears.

It is the one service that is always up, and the only one a person interacts
with. It never parses a CAS: the importer has already done that, which is why
its dependencies omit the UIMA and XML libraries entirely.

## Running it

From the stack root:

```bash
docker compose up -d
```

The webapp is then at <http://localhost:8010>, and `/healthz` answers only when
the database is actually reachable — a process that is up but cannot query is
not healthy from a caller's point of view.

A fresh stack starts with nothing in it. Import something before expecting the
video list to be populated; see
[cas-to-postgres-importer](../cas-to-postgres-importer/README.md).

### Without the rest of the stack

The image builds from this directory alone:

```bash
docker build -t duui-video-emotion-visualization/webapp .
```

Natively, with the project's Python and the requirements installed, `src` is
the source root rather than a package:

```bash
PYTHONPATH=src python -m backend
```

That binds `127.0.0.1:8000`, for looking at it on your own machine. The
container instead runs uvicorn directly, so it can bind every interface and be
configured from outside.

## What it serves

| Path | What it is |
| --- | --- |
| `/` | The frontend, as static files |
| `/media/…` | The video store, read-only, range-request aware so seeking works |
| `/healthz` | Liveness, including a real query against the database |
| `/api/videos` | The video list |
| `/api/videos/{video_id}/data` | Everything the frontend needs to render one video |
| `/api/persons/global` | People linked across videos |
| `/api/stats/{video_id}` | Per-person emotion summaries |
| `/api/jobs` | What the importer or the identity linker is currently doing |
| `/api/ask` | The Ask panel's question endpoint |

One payload per video rather than a request per panel: subtitles, emotions and
boxes all have to stay in step with playback, and fetching them separately is
how they stop being in step.

## Configuring it

Values and defaults are in [configuration.md](../docs/configuration.md). This
service reads:

| | |
| --- | --- |
| Video store | `DUUI_VIDEO_DIR` |
| Database | `DUUI_DB_NAME`, `DUUI_DB_USER`, `DUUI_DB_PASSWORD`, `DUUI_DB_HOST`, `DUUI_DB_CONNECT_TIMEOUT` |
| Ask panel | `DUUI_QUERY_API_KEY`, `DUUI_QUERY_BASE_URL`, `DUUI_QUERY_MODEL`, `DUUI_QUERY_MAX_ROWS`, `DUUI_QUERY_STATEMENT_TIMEOUT_MS`, `DUUI_QUERY_MAX_TOOL_ITERATIONS` |

The Ask panel is optional. Leave `DUUI_QUERY_API_KEY` empty and it reports
itself as unconfigured while everything else works unchanged. When it is
configured, a language model writes SQL that is checked by
`src/backend/query_agent/sql_guard.py` before it is allowed to run.

## Testing it

From the stack root:

```bash
docker compose run --rm tests webapp/tests
```

Much of the suite needs no database at all — the contrast, palette, markup,
stylesheet and script checks are pure functions over committed files, which is
what makes them cheap enough to run on every change:

```bash
docker compose run --rm tests webapp/tests -k contrast
```

The rest runs against the empty database the runner provisions; run `pytest`
some other way and those skip, which the summary says in as many words.

One check is not automated: `tests/a11y_browser_check.js` needs a live browser
and pulls axe-core from a content delivery network, so it stays a manual
procedure. [docs/accessibility.md](docs/accessibility.md) says how to run it.

## The frontend has no build step

`src/frontend/` is served exactly as it is committed — no bundler, no
transpiler, no generated files. Types come from JSDoc comments plus
`// @ts-check`, and `jsconfig.json` is what points `tsc --noEmit` at them, so
the type checking happens without anything being emitted.

Editing a file under `src/frontend/` and reloading the page is the whole
development loop. Static responses carry `Cache-Control: no-cache` so a browser
revalidates rather than serving a stale module against fresh HTML.

## Fonts

Three third-party font families are committed under `src/frontend/fonts/` and
served from this application. The page loads nothing from outside itself: no
font service, no content delivery network, no analytics.

| Family | License | License file |
| --- | --- | --- |
| Oxanium | SIL Open Font License 1.1 | `src/frontend/fonts/oxanium/OFL.txt` |
| Roboto | SIL Open Font License 1.1 | `src/frontend/fonts/roboto/OFL.txt` |
| Ubuntu Mono | Ubuntu Font Licence 1.0 | `src/frontend/fonts/ubuntu-mono/UFL.txt` |

Each license is reproduced verbatim in the family's own directory, beside the
files it covers, so nothing has to be cross-referenced when a license needs
checking or a family needs pulling out. None of the three fonts is modified.

## Where the detail is

- **The layout.** `src/backend/` is the package: `app.py` builds the
  application, `routes/` holds one module per endpoint group, `queries/` the
  SQL behind them, and `query_agent/` the Ask panel — its client loop, the
  schema description the model is given, and the guard that decides whether a
  generated statement may run. `src/frontend/` is the page: `js/panels/` one
  module per sidebar panel, `js/playback/` the player, the overlay and the
  subtitles, `css/` one file per region.
- **Accessibility** — [docs/accessibility.md](docs/accessibility.md), the rules
  to work by and what is still missing. The before-picture is in
  [docs/a11y-baseline/](docs/a11y-baseline/README.md) and what changed in
  [docs/a11y-verification.md](docs/a11y-verification.md).
- **The schema it reads** — [database.md](../docs/database.md).
- **The contracts it shares with the other parts** —
  [architecture.md](../docs/architecture.md).
