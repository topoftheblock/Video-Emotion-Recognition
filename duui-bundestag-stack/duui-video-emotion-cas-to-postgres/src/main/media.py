"""
Places the video file that belongs to a just-imported CAS into
VIDEO_MEDIA_DIR, so the webapp -- which only ever looks in
VIDEO_MEDIA_DIR for `videos.filename` -- automatically has it without
a separate manual copy step.

This is what makes the one-off importer container fully self
-contained: given a CAS in DUUI_INPUT_XMI_DIR, running the importer
once leaves both the DB rows *and* the matching video file in place
for the webapp container to pick up, with `videos.filename` as the
join key between them. See the "Docker architecture" section in
README.md for the full picture.

The video is obtained from whichever of two sources has it, in order:

  1. A real file named `videos.filename` in DUUI_INPUT_VIDEO_DIR.
  2. The CAS itself. DUUI pipelines carry the video base64-encoded in
     a sofa (`mimeType: video/*`) -- the same payload the DUUI
     components pass around, see e.g. the extract-audio component's
     `video_base64` field -- so a CAS exported with its sofa intact
     needs no companion video file at all. Which view that is comes
     from DUUI_VIDEO_VIEW (default `_InitialView`).

(1) is preferred purely because copying a file is cheaper than
base64-decoding tens of megabytes; the result is identical either way.
"""

import base64
import shutil
from pathlib import Path

from .config import VIDEO_MEDIA_DIR, VIDEO_VIEW

# What DUUI_VIDEO_VIEW falls back to when unset -- knowing whether the
# view name was chosen by the user or inherited decides whether "no
# such view in this CAS" is worth warning about.
_DEFAULT_VIDEO_VIEW = "_InitialView"


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
        print(f"[duui_parser] video file already present at {dest}, leaving as-is")
        return dest

    source = Path(source_dir) / video_filename
    if not source.exists():
        print(f"[duui_parser] warning: no source video file at {source}")
        return None

    shutil.copy2(source, dest)
    print(f"[duui_parser] placed video file: {source} -> {dest}")
    return dest


def _sofa_bytes(sofa):
    """
    The raw payload of `sofa`, or None if it carries none.

    Sofa data can arrive two ways: `sofaString` (base64 text, what the
    DUUI video components produce and what the Bundestag CAS uses) or a
    `sofaArray` byte array. Both are handled; anything else is ignored.
    """
    encoded = getattr(sofa, "sofaString", None)
    if encoded:
        # `validate=False`: the payload is machine-generated base64,
        # but pipelines sometimes wrap it in whitespace/newlines,
        # which strict validation would reject outright.
        return base64.b64decode(encoded, validate=False)

    byte_array = getattr(sofa, "sofaArray", None)
    elements = getattr(byte_array, "elements", None)
    if elements:
        return bytes(bytearray(elements))
    return None


def _video_sofa(cas):
    """
    The sofa in `cas` holding the video, as (sofa_id, mime_type,
    data-bytes), or None if the CAS has none.

    DUUI_VIDEO_VIEW (default `_InitialView`) names the view to read.
    Any other `video/*` sofa is used as a fallback, so a pipeline that
    routes the video somewhere unexpected still works without
    configuration -- the setting only has to be reached for when the
    CAS has several video sofas, or the intended one isn't labelled
    `video/*` at all.
    """
    configured = None
    fallback = None

    for view in getattr(cas, "views", []):
        sofa = getattr(view, "sofa", None)
        if sofa is None:
            continue
        sofa_id = getattr(sofa, "sofaID", None) or "?"
        mime = getattr(sofa, "mimeType", None) or ""

        if sofa_id == VIDEO_VIEW:
            configured = (sofa_id, mime, sofa)
        elif fallback is None and mime.startswith("video/"):
            fallback = (sofa_id, mime, sofa)

    if configured is not None:
        sofa_id, mime, sofa = configured
        data = _sofa_bytes(sofa)
        if data and (not mime or mime.startswith("video/")):
            return sofa_id, mime or "video/*", data
        if data:
            # Named view holds something, but it is audio or text --
            # writing that out as a video would produce an unplayable
            # file, so say why it was skipped rather than doing it.
            print(
                f"[duui_parser] warning: DUUI_VIDEO_VIEW='{VIDEO_VIEW}' is a "
                f"'{mime}' sofa, not a video -- ignoring it"
            )
    elif VIDEO_VIEW != _DEFAULT_VIDEO_VIEW:
        # Only worth flagging when explicitly configured: the default
        # view is simply absent from plenty of CAS files.
        print(
            f"[duui_parser] warning: DUUI_VIDEO_VIEW='{VIDEO_VIEW}' is not a "
            f"view in this CAS"
        )

    if fallback is not None:
        sofa_id, mime, sofa = fallback
        data = _sofa_bytes(sofa)
        if data:
            return sofa_id, mime, data
    return None


def extract_video_from_cas(cas, video_filename):
    """
    Write the video embedded in `cas`'s own sofa to
    `<VIDEO_MEDIA_DIR>/<video_filename>`. Returns the destination Path,
    or None if the CAS carries no video payload.

    Used when no companion video file exists on disk -- a CAS exported
    with its sofa intact already contains the bytes, so there is no
    reason to make the user supply the same video twice.

    Deliberately never raises, for the same reason `place_video_file`
    doesn't: a video that can't be recovered costs playback, not the
    import.
    """
    if not video_filename or video_filename == "unknown":
        return None

    try:
        found = _video_sofa(cas)
    except Exception as exc:
        print(f"[duui_parser] warning: could not read video sofa from CAS: {exc}")
        return None
    if found is None:
        return None

    sofa_id, mime, data = found
    if not data:
        return None

    dest_dir = Path(VIDEO_MEDIA_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / video_filename
    try:
        dest.write_bytes(data)
    except OSError as exc:
        print(f"[duui_parser] warning: could not write extracted video to {dest}: {exc}")
        return None

    print(
        f"[duui_parser] extracted video from CAS sofa '{sofa_id}' "
        f"({mime}, {len(data)} bytes) -> {dest}"
    )
    return dest


def ensure_video_available(video_filename, source_dir, cas=None):
    """
    Make `videos.filename` playable by the webapp: copy the companion
    video file if there is one, otherwise fall back to the copy
    embedded in the CAS. Returns the destination Path, or None if
    neither source had the video -- in which case the DB rows are still
    fine, only playback isn't.
    """
    dest = place_video_file(video_filename, source_dir)
    if dest is not None:
        return dest

    if cas is not None:
        dest = extract_video_from_cas(cas, video_filename)
        if dest is not None:
            return dest

    if video_filename and video_filename != "unknown":
        print(
            f"[duui_parser] warning: no video for '{video_filename}' in "
            f"{source_dir} and none embedded in the CAS -- the DB rows were "
            f"still imported, but the webapp won't be able to play it until a "
            f"file with that exact name is placed in {Path(VIDEO_MEDIA_DIR)}"
        )
    return None
