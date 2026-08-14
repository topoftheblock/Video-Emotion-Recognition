"""High-level orchestration: load a CAS, run every parser step against
it inside one DB transaction, commit, then place the companion video
file where the webapp expects it.

`run()` handles one CAS; `run_many()` handles a batch (explicit files
and/or whole directories) and is what `python -m main` actually calls -- it
loads and patches the typesystem exactly once for the entire batch
rather than per file, which dominates startup time otherwise.
"""

import os
from pathlib import Path

from cassis import load_cas_from_xmi
from lxml import etree

from .config import INPUT_VIDEO_DIR, INPUT_XMI_DIR, XMI_FILE
from .db import get_db_connection
from .job_runs import JobRun
from .media import (
    cas_source,
    ensure_video_available,
    find_media_sofas,
    select_video_sofa,
    strip_media_sofas,
)
from .parsers import PARSE_STEPS
from .typesystem import load_merged_typesystem, loading_cas_quietly


def parse_and_insert(cas, cursor, on_step=None):
    """
    Run all registered parser steps against a single loaded CAS.

    `context` is threaded through every step so later steps (Segment,
    Person, Presence, Detection, Emotion, ...) can read
    context["global_video_id"], which the video step resolves first.
    Returned so `run()` can use context["video_filename"] afterwards.

    `on_step(name, index, total)` is called before each step. This is
    the one phase of an import whose progress is actually countable --
    the CAS parse either side of it is a single opaque call -- so it is
    what the status banner shows a bar for.
    """
    context = {}
    for index, step in enumerate(PARSE_STEPS, start=1):
        if on_step is not None:
            on_step(step.__name__.rsplit(".", 1)[-1], index, len(PARSE_STEPS))
        step.parse(cas, cursor, context)
    return context


def default_input_paths():
    """
    What to import when no path is passed on the command line: the
    single file named by DUUI_XMI_FILE if it's set (the older
    one-CAS-at-a-time workflow), otherwise the whole DUUI_INPUT_XMI_DIR
    directory.
    """
    return [XMI_FILE] if XMI_FILE else [INPUT_XMI_DIR]


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


def run(xmi_file=None, typesystem=None, job=None):
    """
    Load one CAS, parse it, commit to the database, and place the video
    file that came alongside it (same directory, same filename as the
    `videos` row) into VIDEO_MEDIA_DIR.

    `typesystem` lets a caller pass an already-loaded, already-patched
    typesystem so a batch doesn't reload it per file; omitted, it's
    loaded here as before.

    `job` is an optional job_runs.JobRun to report phases to. Left out
    (a direct one-file call), the import runs exactly as before and
    nothing is written to `job_runs` -- run_many() is what opens a run.

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
        if job is not None:
            job.update(phase="loading typesystem")
        typesystem = load_merged_typesystem()

    print(f"Loading CAS data from {xmi_file}...")
    # Read the XML first and take the media payloads out of it before
    # cassis ever sees them -- see media.py's docstring for why this is
    # the difference between "imports in a second" and "needs 20 GB".
    # huge_tree, because these documents carry attributes far past
    # libxml2's default limits.
    if job is not None:
        job.update(phase=f"reading {Path(xmi_file).name}")
    tree = etree.parse(str(xmi_file), etree.XMLParser(huge_tree=True))

    sofas = find_media_sofas(tree)
    # Captured before the blanking below, and decoded only if the video
    # turns out not to be on disk already (see ensure_video_available).
    video_payload = select_video_sofa(sofas)
    stripped = strip_media_sofas(sofas, video=video_payload)
    if stripped:
        print(f"[duui_parser] media sofas held back from the CAS: {', '.join(stripped)}")

    # No sub-progress to report here: this is one cassis call, and on a
    # multi-hour export it is usually the longest phase of the import.
    # The phase name plus the elapsed time the viewer shows is the
    # whole of what can honestly be said about it.
    if job is not None:
        job.update(phase=f"parsing {Path(xmi_file).name}")
    with loading_cas_quietly():
        # trusted=True enables lxml's huge_tree parsing, needed for large
        # multi-hour-session XMI exports that exceed lxml's default buffer.
        cas = load_cas_from_xmi(
            cas_source(tree), typesystem=typesystem, lenient=True, trusted=True
        )
    # The tree is 60x the size of what cassis now holds; nothing below
    # needs it, and the payload keeps its own reference to the bytes.
    del tree

    print("Connecting to database and inserting data...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # The step counter goes in the phase text, not in
        # progress_current: that pair counts files for the whole run,
        # and a bar that switched scale halfway through a batch would
        # be worse than no bar.
        def on_step(name, index, total):
            job.update(phase=f"inserting {name} ({index}/{total})")

        context = parse_and_insert(cas, cursor, on_step=on_step if job else None)
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # The video is looked up by the exact filename the CAS records, in
    # DUUI_INPUT_VIDEO_DIR (see README "Docker architecture") -- which
    # may or may not be the same directory the .xmi came from, so the
    # configured location is used rather than the .xmi's own parent.
    # The sofa payload read above is passed as the fallback for a CAS
    # that embeds its own video and has no companion file.
    #
    # Deliberately still after the parse: `videos.filename` is resolved
    # by the video parser, so this stays the one place that decides
    # what the file is called -- the payload was only *captured* early,
    # not interpreted.
    if job is not None:
        job.update(phase=f"placing video for {Path(xmi_file).name}")
    ensure_video_available(context.get("video_filename"), INPUT_VIDEO_DIR, video_payload)

    print(f"Finished {xmi_file}")


def run_many(paths=None):
    """
    Import every CAS in `paths` (any mix of .xmi files and directories
    containing them). Returns (succeeded, failed) as lists of
    (path, error-or-None).

    Each file gets its own transaction, and a failure is reported and
    skipped rather than aborting the batch -- with a folder of exports,
    one malformed file shouldn't cost you every import after it. The
    exit code is left to the caller (see src/main/__main__.py) so a partial failure
    is still visible to a CI job or shell script.

    The whole batch is one `job_runs` row, which is what the viewer
    shows as "an import is running" (see job_runs.py). It is opened
    only once there is actually something to import: a run that found
    no .xmi files has nothing to report and shouldn't flash a banner.
    """
    paths = list(paths) if paths else default_input_paths()
    xmi_files = resolve_xmi_paths(paths)

    if not xmi_files:
        print(f"No .xmi files found in: {', '.join(str(p) for p in paths)}")
        for reason in describe_missing_inputs(paths):
            print(f"  - {reason}")
        return [], []

    with JobRun("importer") as job:
        print("Loading and patching TypeSystems...")
        job.update(phase="loading typesystem", current=0, total=len(xmi_files))
        typesystem = load_merged_typesystem()

        print(f"Importing {len(xmi_files)} CAS file(s)...")
        succeeded, failed = [], []
        for index, xmi_file in enumerate(xmi_files, start=1):
            print(f"\n--- [{index}/{len(xmi_files)}] {xmi_file} ---")
            job.update(current=index - 1, total=len(xmi_files))
            try:
                run(str(xmi_file), typesystem=typesystem, job=job)
                succeeded.append((xmi_file, None))
            except Exception as exc:  # noqa: BLE001 -- batch must survive one bad file
                print(f"[duui_parser] ERROR importing {xmi_file}: {exc}")
                failed.append((xmi_file, exc))

        job.update(
            current=len(xmi_files),
            message=f"{len(succeeded)} imported, {len(failed)} failed",
            force=True,
        )

    print(
        f"\nDone: {len(succeeded)} imported, {len(failed)} failed "
        f"(of {len(xmi_files)} file(s))."
    )
    for xmi_file, exc in failed:
        print(f"  FAILED {xmi_file}: {exc}")
    return succeeded, failed
