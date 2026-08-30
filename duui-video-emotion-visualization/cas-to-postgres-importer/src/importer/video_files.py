"""Putting a video where the webapp can find it.

A video reaches the video store one of two ways: copied from the input
directory, or extracted from the CAS that carried it embedded. Either
way it lands at `<VIDEO_MEDIA_DIR>/<videos.filename>`, which is the only
place the webapp looks.

Reading the CAS itself is `cas/sofas.py`.
"""

import shutil
from pathlib import Path

from .cas.sofas import SofaPayload
from .config import VIDEO_MEDIA_DIR


def place_video_file(video_filename: str | None, source_dir: str | Path) -> Path | None:
    """Copy a video from the input directory into the video store.

    Never raises, deliberately. A missing video file means the webapp
    cannot play that video yet, which the user sees as a normal
    "unavailable" state through `/api/videos`. It should not roll back
    or block an otherwise successful import.

    Args:
        video_filename: The name recorded in `videos.filename`.
        source_dir: The directory to copy from.

    Returns:
        The destination path, or None when there was nothing to do or
        no source file was found.
    """
    if not video_filename or video_filename == "unknown":
        return None

    dest_dir = Path(VIDEO_MEDIA_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / video_filename

    if dest.exists():
        # Already placed: either by an earlier run, or because the
        # source and the video store are the same directory — the
        # default in a native setup — where copying would be wasted I/O.
        print(f"[importer] video file already present at {dest}, leaving as-is")
        return dest

    source = Path(source_dir) / video_filename
    if not source.exists():
        print(f"[importer] warning: no source video file at {source}")
        return None

    shutil.copy2(source, dest)
    print(f"[importer] placed video file: {source} -> {dest}")
    return dest


def extract_video_payload(
    payload: SofaPayload | None, video_filename: str | None
) -> Path | None:
    """Write a sofa's bytes into the video store.

    Used when no companion video file exists on disk. A CAS exported
    with its sofa intact already carries the bytes, so there is no
    reason to make the user supply the same video twice.

    Never raises, for the same reason `place_video_file` does not: a
    video that cannot be recovered costs playback, not the import.

    Args:
        payload: The sofa captured before the CAS was loaded.
        video_filename: The name recorded in `videos.filename`.

    Returns:
        The destination path, or None when there was nothing to write.
    """
    if not video_filename or video_filename == "unknown" or payload is None:
        return None

    try:
        data = payload.data()
    except Exception as exc:  # costs playback, not the import
        print(f"[importer] warning: could not decode the video sofa: {exc}")
        return None
    if not data:
        return None

    dest_dir = Path(VIDEO_MEDIA_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / video_filename
    try:
        dest.write_bytes(data)
    except OSError as exc:
        print(f"[importer] warning: could not write extracted video to {dest}: {exc}")
        return None

    print(
        f"[importer] extracted video from CAS sofa '{payload.sofa_id}' "
        f"({payload.mime or 'video/*'}, {len(data)} bytes) -> {dest}"
    )
    return dest


def ensure_video_available(
    video_filename: str | None,
    source_dir: str | Path,
    payload: SofaPayload | None = None,
) -> Path | None:
    """Make a video playable by the webapp, from either source.

    Copies the companion video file if there is one, and otherwise
    falls back to the copy embedded in the CAS.

    `payload` is decoded only if the first source came up empty, so
    re-importing a video already in the store does no base64 work.

    Args:
        video_filename: The name recorded in `videos.filename`.
        source_dir: The directory to copy from.
        payload: The sofa captured before the CAS was loaded, if any.

    Returns:
        The destination path, or None if neither source had the video —
        in which case the database rows are still fine, and only
        playback is missing.
    """
    dest = place_video_file(video_filename, source_dir)
    if dest is not None:
        return dest

    if payload is not None:
        dest = extract_video_payload(payload, video_filename)
        if dest is not None:
            return dest

    if video_filename and video_filename != "unknown":
        print(
            f"[importer] warning: no video for '{video_filename}' in "
            f"{source_dir} and none embedded in the CAS — the database rows "
            f"were still imported, but the webapp cannot play it until a "
            f"file with that exact name is placed in {Path(VIDEO_MEDIA_DIR)}"
        )
    return None
