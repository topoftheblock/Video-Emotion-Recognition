"""High-level orchestration: load a CAS, run every parser step against
it inside one DB transaction, commit, then place the companion video
file where the webapp expects it.

`run()` handles one CAS; `run_many()` handles a batch (explicit files
and/or whole directories) and is what `python -m main` actually calls -- it
loads and patches the typesystem exactly once for the entire batch
rather than per file, which dominates startup time otherwise.
"""

from collections import Counter
from pathlib import Path

from cassis import load_cas_from_xmi
from lxml import etree

from .cas.sofas import (
    cas_source,
    find_media_sofas,
    read_video_filename,
    select_video_sofa,
    strip_media_sofas,
)
from .cas.typesystem import load_merged_typesystem, loading_cas_quietly
from .config import INPUT_VIDEO_DIR, ON_EXISTING, ON_EXISTING_CHOICES, XMI_FILE
from .db import delete_video, find_video_by_filename, get_db_connection
from .inputs import default_input_paths, describe_missing_inputs, resolve_xmi_paths
from .job_runs import JobRun
from .parsers import PARSE_STEPS
from .video_files import ensure_video_available


def parse_and_insert(cas, cursor, on_step=None, context=None):
    """
    Run all registered parser steps against a single loaded CAS.

    `context` is threaded through every step so later steps (Segment,
    Person, Presence, Detection, Emotion, ...) can read
    context["global_video_id"], which the video step resolves first.
    Returned so `run()` can use context["video_filename"] afterwards.
    A caller can seed it -- run() passes the filename it read off the
    raw XML, so the video row is keyed by the name the skip/replace
    decision was made on.

    `on_step(name, index, total)` is called before each step. This is
    the one phase of an import whose progress is actually countable --
    the CAS parse either side of it is a single opaque call -- so it is
    what the status banner shows a bar for.
    """
    context = {} if context is None else context
    for index, step in enumerate(PARSE_STEPS, start=1):
        if on_step is not None:
            on_step(step.__name__.rsplit(".", 1)[-1], index, len(PARSE_STEPS))
        step.parse(cas, cursor, context)
    return context


def run(xmi_file=None, typesystem=None, job=None, on_existing=None):
    """
    Load one CAS, parse it, commit to the database, and place the video
    file that came alongside it (same directory, same filename as the
    `videos` row) into VIDEO_MEDIA_DIR.

    Returns "imported", "skipped" or "replaced", so a batch can report
    what it actually did.

    `typesystem` lets a caller pass an already-loaded, already-patched
    typesystem so a batch doesn't reload it per file; omitted, it's
    loaded here as before.

    `job` is an optional job_runs.JobRun to report phases to. Left out
    (a direct one-file call), the import runs exactly as before and
    nothing is written to `job_runs` -- run_many() is what opens a run.

    `on_existing` is "skip" or "replace" (default from
    DUUI_ON_EXISTING); see config.py.

    Takes exactly one file -- use `run_many()` for a directory or a
    batch (it's also what handles loading the typesystem only once).
    """
    on_existing = on_existing or ON_EXISTING
    if on_existing not in ON_EXISTING_CHOICES:
        raise ValueError(
            f"on_existing must be one of {', '.join(ON_EXISTING_CHOICES)}, "
            f"not {on_existing!r}"
        )
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
    # cassis ever sees them -- see cas/sofas.py's docstring for why this is
    # the difference between "imports in a second" and "needs 20 GB".
    # huge_tree, because these documents carry attributes far past
    # libxml2's default limits.
    if job is not None:
        job.update(phase=f"reading {Path(xmi_file).name}")
    tree = etree.parse(str(xmi_file), etree.XMLParser(huge_tree=True))

    # The filename is read here, off the raw XML, because it is what
    # decides whether this file needs importing at all -- and answering
    # that before the cassis load is the whole value of `skip`.
    video_filename = read_video_filename(tree)
    replaced = False
    if video_filename:
        existing_video_id = find_video_by_filename(video_filename)
        if existing_video_id is not None:
            if on_existing == "skip":
                print(
                    f"[importer] '{video_filename}' is already imported "
                    f"(video_id {existing_video_id}) -- skipping. Use "
                    f"--on-existing replace to re-import it."
                )
                return "skipped"
            delete_video(existing_video_id)
            replaced = True
            print(
                f"[importer] replacing '{video_filename}' "
                f"(video_id {existing_video_id}): previous rows deleted"
            )

    sofas = find_media_sofas(tree)
    # Captured before the blanking below, and decoded only if the video
    # turns out not to be on disk already (see ensure_video_available).
    video_payload = select_video_sofa(sofas)
    stripped = strip_media_sofas(sofas, video=video_payload)
    if stripped:
        print(f"[importer] media sofas held back from the CAS: {', '.join(stripped)}")

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

        # Seeded with the name the pre-pass read, so the row the video
        # parser upserts is keyed by the same filename the skip/replace
        # decision above was made on.
        context = {"video_filename": video_filename}
        context = parse_and_insert(
            cas, cursor, on_step=on_step if job else None, context=context
        )
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
    ensure_video_available(
        context.get("video_filename"), INPUT_VIDEO_DIR, video_payload
    )

    print(f"Finished {xmi_file}")
    return "replaced" if replaced else "imported"


def run_many(paths=None, on_existing=None):
    """
    Import every CAS in `paths` (any mix of .xmi files and directories
    containing them). Returns (succeeded, failed) as lists of
    (path, error-or-None) -- a skipped file counts as succeeded, since
    "already imported" is a successful outcome, not a failure.

    Each file gets its own transaction, and a failure is reported and
    skipped rather than aborting the batch -- with a folder of exports,
    one malformed file shouldn't cost you every import after it. The
    exit code is left to the caller (see src/importer/__main__.py) so a partial failure
    is still visible to a CI job or shell script.

    `on_existing` ("skip"/"replace", default DUUI_ON_EXISTING) decides
    what happens to a file whose video is already in the database.

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
        outcomes = Counter()
        for index, xmi_file in enumerate(xmi_files, start=1):
            print(f"\n--- [{index}/{len(xmi_files)}] {xmi_file} ---")
            job.update(current=index - 1, total=len(xmi_files))
            try:
                outcome = run(
                    str(xmi_file),
                    typesystem=typesystem,
                    job=job,
                    on_existing=on_existing,
                )
                outcomes[outcome] += 1
                succeeded.append((xmi_file, None))
            except Exception as exc:  # noqa: BLE001 -- batch must survive one bad file
                print(f"[importer] ERROR importing {xmi_file}: {exc}")
                failed.append((xmi_file, exc))

        outcomes["failed"] = len(failed)
        summary = (
            ", ".join(f"{count} {name}" for name, count in outcomes.items() if count)
            or "nothing to do"
        )
        job.update(current=len(xmi_files), message=summary, force=True)

    print(f"\nDone: {summary} (of {len(xmi_files)} file(s)).")
    for xmi_file, exc in failed:
        print(f"  FAILED {xmi_file}: {exc}")
    return succeeded, failed
