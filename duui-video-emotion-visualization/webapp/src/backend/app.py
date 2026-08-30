"""The FastAPI application: what the webapp serves, and in what order.

Two things reach the browser:

1. The video file itself, from the video store, range-request aware so
   that seeking works.
2. One JSON payload per video carrying everything the frontend needs to
   render subtitles, emotions and bounding boxes in step with playback:
   sentence segments with their assembled text, per-modality emotions,
   and the detections.

`create_app` is a factory rather than a module-level `app` so that
importing this package has no side effects. The directory creation and
the static mounts, which fail on a missing directory, happen when an
app is built and not when a test imports a helper. Run it with
uvicorn's `--factory` flag, as the Dockerfile does:

    uvicorn backend.app:create_app --factory
"""

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from .config import STATIC_DIR, VIDEO_DIR
from .db import get_db_connection
from .queries import jobs as jobs_query
from .routes import ask, jobs, persons, stats, videos


class NoCacheStaticFiles(StaticFiles):
    """Static files the browser must revalidate on every load.

    The frontend is unversioned — `index.html` asks for `js/main.js`,
    not `js/main.<hash>.js` — so a browser is free to reuse a cached
    copy under its own heuristics, and does: after a rebuild it can
    revalidate the navigation, getting fresh HTML, while serving the
    module and stylesheet subresources from its disk cache. The result
    is a page whose HTML has a new control on it and whose JavaScript
    has never heard of that control, which looks like a broken feature
    rather than a stale cache.

    `no-cache` does not mean "do not store". The copy is kept, and the
    ETag `StaticFiles` already sends still turns the check into a 304,
    so this costs one conditional request per file rather than a
    re-download.
    """

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        """Serve the file, adding the revalidation header."""
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app() -> FastAPI:
    """Build the application: mounts, routes, and the startup checks.

    Returns:
        The configured application, ready to serve.
    """
    # The video store, which the importer writes and this reads. It is
    # mounted read-only, so this call only ever succeeds because the
    # image already created the directory and gave it to the runner.
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="DUUI Video Emotion Visualization")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Report liveness, and that the database is actually reachable.

        Deliberately runs a real query rather than answering "the
        process is up": a webapp that is running but cannot reach
        Postgres is not healthy from a caller's point of view.

        Raises:
            HTTPException: 503, when the database cannot be reached.
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

    # The jobs write this table, but the webapp is the service that is
    # always up, and the schema only runs on a fresh volume — so the
    # webapp creates it too, for a database that predates the feature.
    # Best-effort: a failure here must not stop the app from starting.
    jobs_query.ensure_table()

    app.include_router(videos.router)
    app.include_router(persons.router)
    app.include_router(stats.router)
    app.include_router(ask.router)
    app.include_router(jobs.router)

    # Mounted last: "/" is a catch-all, so anything registered after it
    # would never be reached.
    app.mount("/media", StaticFiles(directory=VIDEO_DIR), name="media")
    app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app
