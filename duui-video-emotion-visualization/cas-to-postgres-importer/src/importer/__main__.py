#!/usr/bin/env python3
"""Entry point for the importer.

`src/` is the source root — it goes on the path, it is not a package —
so this runs as the `importer` package's entry module, with `src/` on
PYTHONPATH or from inside it:

    python -m importer                        # uses DUUI_XMI_FILE
    python -m importer path/to/file.xmi       # one CAS
    python -m importer cas/                   # every *.xmi in there
    python -m importer a.xmi b.xmi cas/more/  # any mix of the two

A file whose video is already in the database, matched by filename, is
skipped by default, so re-running over a drop directory imports only
what is new. Pass `--on-existing replace` to re-import it instead: the
existing video and everything hanging off it is deleted first, so the
rows match the CAS being imported rather than merging two exports.

    python -m importer cas/ --on-existing replace

The same setting is available as DUUI_ON_EXISTING for the Compose
services; see docker-compose.yml.

Each CAS is expected to sit beside its source video, under the filename
the CAS itself carries. That video is placed in the video store for the
webapp, so pointing this at a directory of CAS files plus their videos
imports the whole batch in one go.

Files are imported one transaction each: a malformed CAS is reported
and skipped rather than aborting the rest of the batch. The process
exits non-zero if anything failed, so a script or CI job notices a
partial import.

Configuration — database credentials, typesystem paths, the default
input path — is read from `config.py` and can be overridden through the
`DUUI_*` environment variables listed there.
"""

import sys

from importer.config import ON_EXISTING_CHOICES
from importer.pipeline import run_many


def _split_args(argv: list[str]) -> tuple[list[str], str | None]:
    """Separate `--on-existing <mode>` from the paths.

    Hand-parsed rather than with argparse: the positional half is "any
    number of files and directories", and argparse would want to own
    `-h` and prefix matching for a command line whose entire surface is
    this one flag.

    Args:
        argv: The arguments, without the program name.

    Returns:
        The paths, and the requested mode or None.

    Raises:
        SystemExit: If the flag is missing its value or names an
            unknown mode.
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
