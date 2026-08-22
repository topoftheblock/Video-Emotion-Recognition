"""Putting a video where the webapp can find it.

A video reaches the store one of two ways: copied from the input directory, or
extracted from the CAS that carried it embedded. Either way it lands at
`<VIDEO_MEDIA_DIR>/<videos.filename>`, which is the only place the webapp looks.

Reading the CAS itself is `cas/sofas.py`.
"""

import shutil
from pathlib import Path

from .config import VIDEO_MEDIA_DIR

def place_video_file(video_filename, source_dir):
    """
    Copy `<source_dir>/<video_filename>` to `<VIDEO_MEDIA_DIR>/<video_filename>`
    if it isn't already there. Returns the destination Path on success,
    or None if there was nothing to do (no filename) or no source file
    was found to copy.

    Deliberately never raises: a missing video file means the webapp
    just won't be able to play that video yet (visible to the user as
    a normal "video unavailable" state, see the /api/videos
    `video_file_available` field) -- it shouldn't roll back or block
    an otherwise-successful DB import.
    """
    if not video_filename or video_filename == "unknown":
        return None

    dest_dir = Path(VIDEO_MEDIA_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / video_filename

    if dest.exists():
        # Already placed -- either a previous run of this same import,
        # or source_dir (DUUI_INPUT_VIDEO_DIR) and VIDEO_MEDIA_DIR are
        # the same directory (the default, native-setup case), where
        # copying onto itself would only be wasted I/O.
        print(f"[importer] video file already present at {dest}, leaving as-is")
        return dest

    source = Path(source_dir) / video_filename
    if not source.exists():
        print(f"[importer] warning: no source video file at {source}")
        return None

    shutil.copy2(source, dest)
    print(f"[importer] placed video file: {source} -> {dest}")
    return dest


def extract_video_payload(payload, video_filename):
    """
    Write `payload`'s bytes to `<VIDEO_MEDIA_DIR>/<video_filename>`.
    Returns the destination Path, or None if there was nothing to
    write.

    Used when no companion video file exists on disk -- a CAS exported
    with its sofa intact already contains the bytes, so there is no
    reason to make the user supply the same video twice.

    Deliberately never raises, for the same reason `place_video_file`
    doesn't: a video that can't be recovered costs playback, not the
    import.
    """
    if not video_filename or video_filename == "unknown" or payload is None:
        return None

    try:
        data = payload.data()
    except Exception as exc:  # noqa: BLE001 -- playback, not the import
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


def ensure_video_available(video_filename, source_dir, payload=None):
    """
    Make `videos.filename` playable by the webapp: copy the companion
    video file if there is one, otherwise fall back to the copy that
    was embedded in the CAS. Returns the destination Path, or None if
    neither source had the video -- in which case the DB rows are still
    fine, only playback isn't.

    `payload` is the sofa captured before the CAS was loaded (see
    find_media_sofas/select_video_sofa). It is still only decoded if
    the first source came up empty, so a re-import of a video already
    in the store does no base64 work at all.
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
            f"{source_dir} and none embedded in the CAS -- the DB rows were "
            f"still imported, but the webapp won't be able to play it until a "
            f"file with that exact name is placed in {Path(VIDEO_MEDIA_DIR)}"
        )
    return None
