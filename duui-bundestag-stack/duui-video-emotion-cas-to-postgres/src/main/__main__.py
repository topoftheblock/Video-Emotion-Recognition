#!/usr/bin/env python3
"""
Entry point for the DUUI CAS-to-Postgres importer.

`src/` is the source root (it goes on the path, it is not a package),
so this runs as the `main` package's entry module -- with `src/` on
PYTHONPATH, or from inside it:

    python -m main                        # uses DUUI_XMI_FILE from .env
    python -m main path/to/file.xmi       # one CAS
    python -m main cas/                   # every *.xmi in that directory
    python -m main a.xmi b.xmi cas/more/  # any mix of files and directories

Each CAS is expected to sit next to its source video (the filename the
CAS itself carries), which gets placed into DUUI_VIDEO_DIR for the
webapp -- so pointing this at a directory of .xmi files plus their
videos imports the whole batch in one go.

Files are imported one transaction each: a malformed CAS is reported
and skipped rather than aborting the rest of the batch. Exits non-zero
if anything failed, so a script or CI job notices a partial import.

Configuration (DB credentials, typesystem paths, default XMI path) is
read from src/main/config.py, and can be overridden via the
environment variables listed there (DUUI_DB_NAME, DUUI_XMI_FILE, etc.)
"""

import sys

from main.pipeline import run_many

if __name__ == "__main__":
    _, failed = run_many(sys.argv[1:])
    sys.exit(1 if failed else 0)
