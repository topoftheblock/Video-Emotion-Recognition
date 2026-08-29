#!/usr/bin/env python3
"""Entry point for running the webapp directly.

`src/` is the source root — it goes on the path, it is not a package —
so this runs as the `backend` package's entry module, with `src/` on
PYTHONPATH or from inside it:

    python -m backend                 # serves on 127.0.0.1:8000

That binds to localhost, for looking at it on your own machine. The
container instead runs uvicorn directly, so it can bind every interface
and be configured from outside; see this directory's Dockerfile.

Configuration — database credentials, the video store, the query
agent's endpoint and key — is read from `config.py` and can be
overridden through the `DUUI_*` environment variables listed there.
"""

import uvicorn

from .app import create_app


def main() -> None:
    """Serve the application on localhost."""
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
