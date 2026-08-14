#!/usr/bin/env python3
"""
Entry point for the DUUI video review viewer.

`src/` is the source root (it goes on the path, it is not a package),
so this runs as the `backend` package's entry module -- with `src/` on
PYTHONPATH, or from inside it:

    python -m backend                 # serves on 127.0.0.1:8000

That binds to localhost, for looking at it on your own machine. The
container instead runs uvicorn directly so it can bind 0.0.0.0 and be
reloaded/configured from the outside (see this folder's Dockerfile):

    uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8000

Configuration (DB credentials, video store, the query agent's endpoint
and key) is read from src/backend/config.py, and can be overridden via
the environment variables listed there (DUUI_DB_NAME, DUUI_VIDEO_DIR,
DUUI_QUERY_API_KEY, etc.)
"""

import uvicorn

from .app import create_app


def main():
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
