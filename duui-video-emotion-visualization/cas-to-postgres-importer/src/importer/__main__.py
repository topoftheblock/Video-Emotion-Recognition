#!/usr/bin/env python3
"""
Entry point for the DUUI CAS-to-Postgres importer.

`src/` is the source root (it goes on the path, it is not a package),
so this runs as the `importer` package's entry module -- with `src/` on
PYTHONPATH, or from inside it:

    python -m main                        # uses DUUI_XMI_FILE from .env
    python -m main path/to/file.xmi       # one CAS
    python -m main cas/                   # every *.xmi in that directory
    python -m main a.xmi b.xmi cas/more/  # any mix of files and directories

A file whose video (by filename) is already in the database is skipped
by default, so re-running over a drop folder only imports what is new.
Pass `--on-existing replace` to re-import it instead -- the existing
video and everything hanging off it is deleted first, so the rows match
the CAS being imported rather than merging two exports:

    python -m main cas/ --on-existing replace

The same setting is available as DUUI_ON_EXISTING for the compose
services (see docker-compose.yml).

Each CAS is expected to sit next to its source video (the filename the
CAS itself carries), which gets placed into DUUI_VIDEO_DIR for the
webapp -- so pointing this at a directory of .xmi files plus their
videos imports the whole batch in one go.

Files are imported one transaction each: a malformed CAS is reported
and skipped rather than aborting the rest of the batch. Exits non-zero
if anything failed, so a script or CI job notices a partial import.

Configuration (DB credentials, typesystem paths, default XMI path) is
read from src/importer/config.py, and can be overridden via the
environment variables listed there (DUUI_DB_NAME, DUUI_XMI_FILE, etc.)
"""

import sys

from importer.config import ON_EXISTING_CHOICES
from importer.pipeline import run_many


def _split_args(argv):
    """
    Pull `--on-existing <mode>` out of the argument list; everything
    else is a path.

    Hand-parsed rather than argparse: the positional half is "any
    number of files and/or directories", and argparse would want to
    own `-h`/prefix matching for a CLI whose entire surface is this one
    flag.
    """
    paths = []
    on_existing = None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--on-existing":
            if not args:
                raise SystemExit(
                    f"--on-existing needs a mode: {', '.join(ON_EXISTING_CHOICES)}"
                )
            on_existing = args.pop(0)
        elif arg.startswith("--on-existing="):
            on_existing = arg.split("=", 1)[1]
        else:
            paths.append(arg)

    if on_existing is not None and on_existing not in ON_EXISTING_CHOICES:
        raise SystemExit(
            f"--on-existing must be one of {', '.join(ON_EXISTING_CHOICES)}, "
            f"not {on_existing!r}"
        )
    return paths, on_existing


if __name__ == "__main__":
    paths, on_existing = _split_args(sys.argv[1:])
    _, failed = run_many(paths, on_existing=on_existing)
    sys.exit(1 if failed else 0)
