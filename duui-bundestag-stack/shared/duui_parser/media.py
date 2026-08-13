"""
Places the video file that belongs to a just-imported CAS into
VIDEO_MEDIA_DIR, so the webapp -- which only ever looks in
VIDEO_MEDIA_DIR for `videos.filename` -- automatically has it without
a separate manual copy step.

This is what makes the one-off importer container fully self
-contained: given a CAS-plus-video pair dropped in the input directory
(e.g. `cas/`), running the importer once leaves both the DB rows *and*
the matching video file in place for the webapp container to pick up,
with `videos.filename` as the join key between them. See the "Docker
architecture" section in README.md for the full picture.
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
        # or source_dir and VIDEO_MEDIA_DIR are the same directory
        # (the default, native-setup case), where copying onto itself
        # would only be wasted I/O.
        print(f"[duui_parser] video file already present at {dest}, leaving as-is")
        return dest

    source = Path(source_dir) / video_filename
    if not source.exists():
        print(
            f"[duui_parser] warning: no source video found at {source} -- "
            f"the DB row for '{video_filename}' was still imported, but the "
            f"webapp won't be able to play it until a file with that exact "
            f"name is placed in {dest_dir}"
        )
        return None

    shutil.copy2(source, dest)
    print(f"[duui_parser] placed video file: {source} -> {dest}")
    return dest
