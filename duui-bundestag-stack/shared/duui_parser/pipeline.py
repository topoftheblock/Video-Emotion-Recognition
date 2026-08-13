"""High-level orchestration: load a CAS, run every parser step against
it inside one DB transaction, commit, then place the companion video
file where the webapp expects it.

`run()` handles one CAS; `run_many()` handles a batch (explicit files
and/or whole directories) and is what `main.py` actually calls -- it
loads and patches the typesystem exactly once for the entire batch
rather than per file, which dominates startup time otherwise.
"""

import os
from pathlib import Path

from cassis import load_cas_from_xmi

from .config import INPUT_DIR, XMI_FILE
from .db import get_db_connection
from .media import place_video_file
from .parsers import PARSE_STEPS
from .typesystem import load_merged_typesystem


def parse_and_insert(cas, cursor, conn):
    """
    Run all registered parser steps against a single loaded CAS.

    `context` is threaded through every step so later steps (Segment,
    Person, Presence, Detection, Emotion, ...) can read
    context["global_video_id"], which the video step resolves first.
    Returned so `run()` can use context["video_filename"] afterwards.
    """
    context = {}
    for step in PARSE_STEPS:
        step.parse(cas, cursor, conn, context)
    return context


def default_input_paths():
    """
    What to import when no path is passed on the command line: the
    single file named by DUUI_XMI_FILE if it's set (the older
    one-CAS-at-a-time workflow), otherwise the whole DUUI_INPUT_DIR
    directory.
    """
    return [XMI_FILE] if XMI_FILE else [INPUT_DIR]


def resolve_xmi_paths(paths):
    """
    Expand a mix of file and directory paths into a concrete, sorted,
    de-duplicated list of .xmi files.

    A directory contributes every `*.xmi` directly inside it (not
    recursive -- a CAS and its companion video live side by side in one
    flat drop directory, so recursing would only risk picking up
    unrelated exports). An explicitly named file is taken as-is even if
    it doesn't end in .xmi, since naming it is already an unambiguous
    instruction.
    """
    resolved = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            resolved.extend(sorted(path.glob("*.xmi")))
        else:
            resolved.append(path)

    seen = set()
    unique = []
    for path in resolved:
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def describe_missing_inputs(paths):
    """
    Explain, one line per path, why `resolve_xmi_paths` found nothing.

    `Path.glob` swallows OSError, so it reports an unreadable directory
    exactly the way it reports an empty one: by yielding nothing. That
    collapses three very different failures -- a host path that doesn't
    exist (Docker then mounts an empty directory over it), a mount the
    container isn't allowed to read, and a drop folder that genuinely
    holds no CAS -- into one indistinguishable "no .xmi files" symptom.

    This re-walks the same paths with the errors left in, so the caller
    can name the actual cause instead of the symptom.
    """
    reasons = []
    for raw in paths:
        path = Path(raw)

        if not path.exists():
            reasons.append(f"{path}: does not exist")
            continue

        if not path.is_dir():
            reasons.append(f"{path}: exists but is not a directory")
            continue

        try:
            entries = sorted(os.listdir(path))
        except OSError as exc:
            # The container/user can stat the directory but not list it
            # -- a mount permission problem, not a missing-file problem.
            reasons.append(
                f"{path}: directory exists but cannot be read "
                f"({exc.strerror}) -- check the mount's permissions"
            )
            continue

        if not entries:
            reasons.append(
                f"{path}: directory is empty "
                "-- check that the host path mounted here is the one you meant"
            )
            continue

        preview = ", ".join(entries[:5])
        if len(entries) > 5:
            preview += f", ... (+{len(entries) - 5} more)"
        reasons.append(
            f"{path}: holds {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}, "
            f"none named *.xmi ({preview})"
        )

    return reasons


def run(xmi_file=None, typesystem=None):
    """
    Load one CAS, parse it, commit to the database, and place the video
    file that came alongside it (same directory, same filename as the
    `videos` row) into VIDEO_MEDIA_DIR.

    `typesystem` lets a caller pass an already-loaded, already-patched
    typesystem so a batch doesn't reload it per file; omitted, it's
    loaded here as before.

    Takes exactly one file -- use `run_many()` for a directory or a
    batch (it's also what handles loading the typesystem only once).
    """
    xmi_file = xmi_file or XMI_FILE
    if not xmi_file:
        raise ValueError(
            "run() needs a single .xmi path (or DUUI_XMI_FILE set). "
            "To import a whole directory, use run_many([...]) instead."
        )
    if Path(xmi_file).is_dir():
        raise ValueError(
            f"run() takes one .xmi file, but {xmi_file} is a directory -- "
            "use run_many([...]) to import a directory."
        )

    if typesystem is None:
        print("Loading and patching TypeSystems...")
        typesystem = load_merged_typesystem()

    print(f"Loading CAS data from {xmi_file}...")
    with open(xmi_file, "rb") as f:
        # trusted=True enables lxml's huge_tree parsing, needed for large
        # multi-hour-session XMI exports that exceed lxml's default buffer.
        cas = load_cas_from_xmi(f, typesystem=typesystem, lenient=True, trusted=True)

    print("Connecting to database and inserting data...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        context = parse_and_insert(cas, cursor, conn)
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # A CAS always arrives paired with its source video in the same
    # input directory (see README "Docker architecture") -- look for
    # it right next to the .xmi file just parsed.
    place_video_file(context.get("video_filename"), Path(xmi_file).parent)

    print(f"Finished {xmi_file}")


def run_many(paths=None):
    """
    Import every CAS in `paths` (any mix of .xmi files and directories
    containing them). Returns (succeeded, failed) as lists of
    (path, error-or-None).

    Each file gets its own transaction, and a failure is reported and
    skipped rather than aborting the batch -- with a folder of exports,
    one malformed file shouldn't cost you every import after it. The
    exit code is left to the caller (see main.py) so a partial failure
    is still visible to a CI job or shell script.
    """
    paths = list(paths) if paths else default_input_paths()
    xmi_files = resolve_xmi_paths(paths)

    if not xmi_files:
        print(f"No .xmi files found in: {', '.join(str(p) for p in paths)}")
        for reason in describe_missing_inputs(paths):
            print(f"  - {reason}")
        return [], []

    print("Loading and patching TypeSystems...")
    typesystem = load_merged_typesystem()

    print(f"Importing {len(xmi_files)} CAS file(s)...")
    succeeded, failed = [], []
    for index, xmi_file in enumerate(xmi_files, start=1):
        print(f"\n--- [{index}/{len(xmi_files)}] {xmi_file} ---")
        try:
            run(str(xmi_file), typesystem=typesystem)
            succeeded.append((xmi_file, None))
        except Exception as exc:  # noqa: BLE001 -- batch must survive one bad file
            print(f"[duui_parser] ERROR importing {xmi_file}: {exc}")
            failed.append((xmi_file, exc))

    print(
        f"\nDone: {len(succeeded)} imported, {len(failed)} failed "
        f"(of {len(xmi_files)} file(s))."
    )
    for xmi_file, exc in failed:
        print(f"  FAILED {xmi_file}: {exc}")
    return succeeded, failed
