"""Orchestration: load a CAS, parse it, commit, place its video.

Every parser step runs against one loaded CAS inside a single database
transaction. Only once that commits does the companion video file get
placed where the webapp expects it.

`run()` handles one CAS. `run_many()` handles a batch of files and
directories, and is what `python -m importer` calls: it loads and
patches the typesystem once for the whole batch rather than per file,
which otherwise dominates startup time.
"""

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cassis import Cas, load_cas_from_xmi
from cassis.typesystem import TypeSystem
from lxml import etree
from psycopg2.extensions import cursor as Cursor

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


def parse_and_insert(
    cas: Cas,
    cursor: Cursor,
    on_step: Callable[[str, int, int], None] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run every registered parser step against one loaded CAS.

    The context is threaded through all of them, so later steps can read
    `context["global_video_id"]`, which the video step resolves first.
    A caller may seed it: `run` passes the filename it read off the raw
    XML, so the video row is keyed by the same name the skip or replace
    decision was made on.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        on_step: Called as `(step name, index, total)` before each step.
            This is the one phase of an import whose progress is
            countable — the CAS parse on either side of it is a single
            opaque call — so it is what the webapp draws a bar for.
        context: The shared context, created empty if not given.

    Returns:
        The context, so the caller can read what the steps resolved.
    """
    context = {} if context is None else context
    for index, step in enumerate(PARSE_STEPS, start=1):
        if on_step is not None:
            on_step(step.__name__.rsplit(".", 1)[-1], index, len(PARSE_STEPS))
        step.parse(cas, cursor, context)
    return context


def run(
    xmi_file: str | None = None,
    typesystem: TypeSystem | None = None,
    job: "JobRun | None" = None,
    on_existing: str | None = None,
) -> str:
    """Import one CAS: parse it, commit it, then place its video.

    Takes exactly one file. Use `run_many` for a directory or a batch,
    which is also what loads the typesystem only once.

    Args:
        xmi_file: The CAS to import; defaults to DUUI_XMI_FILE.
        typesystem: An already loaded and patched typesystem, so a batch
            does not reload it per file. Loaded here when omitted.
        job: A job run to report phases to. Without one, nothing is
            written to `job_runs` — `run_many` is what opens a run.
        on_existing: "skip" or "replace"; defaults to DUUI_ON_EXISTING.

    Returns:
        "imported", "skipped" or "replaced", so a batch can report what
        it actually did.

    Raises:
        ValueError: If no file is named, a directory is named, or
            `on_existing` is not a known mode.
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
            f"run() takes one .xmi file, but {xmi_file} is a directory — "
            "use run_many([...]) to import a directory."
        )

    if typesystem is None:
        print("Loading and patching TypeSystems...")
        if job is not None:
            job.update(phase="loading typesystem")
        typesystem = load_merged_typesystem()

    print(f"Loading CAS data from {xmi_file}...")
    # Read the XML and take the media payloads out of it before cassis
    # ever sees them — `cas/sofas.py` explains why that is the
    # difference between an import that fits in memory and one that
    # does not. huge_tree, because these documents carry attributes far
    # past libxml2's default limits.
    if job is not None:
        job.update(phase=f"reading {Path(xmi_file).name}")
    tree = etree.parse(str(xmi_file), etree.XMLParser(huge_tree=True))

    # Read off the raw XML, because this is what decides whether the
    # file needs importing at all — and answering that before the
    # cassis load is the whole value of `skip`.
    video_filename = read_video_filename(tree)
    replaced = False
    if video_filename:
        existing_video_id = find_video_by_filename(video_filename)
        if existing_video_id is not None:
            if on_existing == "skip":
                print(
                    f"[importer] '{video_filename}' is already imported "
                    f"(video_id {existing_video_id}) — skipping. Use "
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

    # No sub-progress here: this is one cassis call, and on a long
    # export it is usually the longest phase of the import. The phase
    # name plus the elapsed time the webapp shows is the whole of what
    # can honestly be said about it.
    if job is not None:
        job.update(phase=f"parsing {Path(xmi_file).name}")
    with loading_cas_quietly():
        # trusted=True enables huge_tree parsing, which long exports
        # need: they exceed lxml's default buffer.
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
        # Bound to a local name so the closure carries a non-optional
        # reference: it is only ever installed when there is a run.
        reporting_to = job

        def on_step(name: str, index: int, total: int) -> None:
            """Report which parser step is running, into the job run."""
            assert reporting_to is not None
            reporting_to.update(phase=f"inserting {name} ({index}/{total})")

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

    # Looked up by the exact filename the CAS records, in
    # DUUI_INPUT_VIDEO_DIR — which need not be the directory the CAS
    # came from, so the configured location is used rather than the
    # file's own parent. The sofa payload captured above is the
    # fallback, for a CAS that embeds its video and has no companion
    # file.
    #
    # Deliberately after the parse: `videos.filename` is resolved by
    # the video parser, so this stays the one place deciding what the
    # file is called. The payload was only *captured* early, never
    # interpreted.
    if job is not None:
        job.update(phase=f"placing video for {Path(xmi_file).name}")
    ensure_video_available(
        context.get("video_filename"), INPUT_VIDEO_DIR, video_payload
    )

    print(f"Finished {xmi_file}")
    return "replaced" if replaced else "imported"


def run_many(
    paths: list[str] | None = None, on_existing: str | None = None
) -> tuple[list[tuple[Path, None]], list[tuple[Path, Exception]]]:
    """Import every CAS in `paths`, one transaction each.

    A failure is reported and skipped rather than aborting the batch:
    given a directory of exports, one malformed file should not cost
    every import after it. The exit code is left to the caller, so a
    partial failure stays visible to a script or CI job.

    The whole batch is one `job_runs` row, which is what the webapp
    shows as an import in progress. It is opened only once there is
    something to import: a run that found no CAS files has nothing to
    report and should not flash a banner.

    Args:
        paths: Any mix of CAS files and directories holding them.
            Defaults to `default_input_paths()`.
        on_existing: "skip" or "replace"; defaults to DUUI_ON_EXISTING.

    Returns:
        The succeeded and failed lists, each of `(path, error)` pairs.
        A skipped file counts as succeeded: "already imported" is a
        successful outcome, not a failure.
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
        outcomes: Counter[str] = Counter()
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
            except Exception as exc:  # the batch must survive one bad file
                print(f"[importer] ERROR importing {xmi_file}: {exc}")
                failed.append((xmi_file, exc))

        outcomes["failed"] = len(failed)
        summary = (
            ", ".join(f"{count} {name}" for name, count in outcomes.items() if count)
            or "nothing to do"
        )
        job.update(current=len(xmi_files), message=summary, force=True)

    print(f"\nDone: {summary} (of {len(xmi_files)} file(s)).")
    for xmi_file, error in failed:
        print(f"  FAILED {xmi_file}: {error}")
    return succeeded, failed
