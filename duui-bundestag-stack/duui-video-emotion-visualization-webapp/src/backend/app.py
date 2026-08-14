"""
Web viewer backend for the DUUI Bundestag pipeline.

Serves two things:
  1. The video file itself, from VIDEO_DIR (range-request aware, so
     seeking works) -- see .env's DUUI_VIDEO_DIR.
  2. A single JSON payload per video with everything the frontend
     needs to render subtitles, emotions, and bounding boxes in sync
     with video playback time: sentences (with assembled subtitle
     text), per-modality emotions, and face/person detections.

`create_app()` is a factory rather than a module-level `app` so that
importing this package has no side effects -- the VIDEO_DIR mkdir and
the static mounts (which fail on a missing directory) happen when an
app is built, not when a test imports a helper. Run it with uvicorn's
--factory flag, as the Dockerfile does:

    uvicorn backend.app:create_app --factory --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from .config import STATIC_DIR, VIDEO_DIR
from .db import get_db_connection
from .routes import ask, persons, stats, videos


class NoCacheStaticFiles(StaticFiles):
    """
    Static files the browser must revalidate on every load.

    The frontend is unversioned -- index.html asks for `js/main.js`,
    not `js/main.<hash>.js` -- so a browser is free to reuse a cached
    copy under its own heuristics. It does: after a rebuild, Chrome
    revalidates the navigation (fresh index.html) while serving the
    module and stylesheet subresources straight from disk cache. The
    result is a page whose HTML has a new control on it and whose JS
    has never heard of that control, which looks exactly like a broken
    feature rather than a stale cache.

    `no-cache` does not mean "don't store" -- the copy is kept and the
    ETag StaticFiles already sends still turns the check into a 304, so
    this costs one conditional request per file, not a re-download.
    """

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app() -> FastAPI:
    # Same DUUI_VIDEO_DIR the importer writes into
    # (duui-video-emotion-cas-to-postgres/src/main/media.py) -- this is
    # the single place both sides agree a video for
    # `videos.filename = X` lives at `<VIDEO_DIR>/X`. See config.py's
    # VIDEO_MEDIA_DIR comment and README "Docker architecture".
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="DUUI Bundestag Video Viewer")

    @app.get("/healthz")
    def healthz():
        """
        Liveness + DB-connectivity check for orchestrators/`docker
        compose healthcheck` -- deliberately does a real query, not just
        "the process is up", since a webapp that's running but can't
        reach Postgres is not actually healthy from a caller's
        perspective.
        """
        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            finally:
                conn.close()
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"database unreachable: {exc}"
            ) from exc
        return {"status": "ok"}

    app.include_router(videos.router)
    app.include_router(persons.router)
    app.include_router(stats.router)
    app.include_router(ask.router)

    # Mounted last: "/" is a catch-all, so anything registered after it
    # would never be reached.
    app.mount("/media", StaticFiles(directory=VIDEO_DIR), name="media")
    app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
