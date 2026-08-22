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

Those payloads are read straight off the XML, before the CAS is handed
to cassis, and blanked in the copy cassis does get. That is not an
optimisation -- it is what makes these files importable at all. cassis
turns every feature structure into Python objects, and a sofa holding a
169 MB base64 video costs upwards of 20 GB that way (measured: killed
at a 20 GB cgroup limit while the same file parses in 0.63 GB with lxml
alone). Blanking the media sofas takes the document cassis sees from
181 MB to 11 MB and the load from "impossible" to under a second, with
no effect on the annotations, which live in the views' member lists
rather than in the sofa. See README "Large CAS files".

The file on disk is never modified: the blanking happens in an
in-memory tree, and the input directory is mounted read-only anyway.
"""

import base64
import shutil
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from lxml import etree

from .config import VIDEO_MEDIA_DIR, VIDEO_VIEW

# What DUUI_VIDEO_VIEW falls back to when unset -- knowing whether the
# view name was chosen by the user or inherited decides whether "no
# such view in this CAS" is worth warning about.
_DEFAULT_VIDEO_VIEW = "_InitialView"

# XMI ids are namespaced; sofaArray is a reference to a ByteArray
# element carried elsewhere in the document, so resolving it needs a
# lookup by that id.
_XMI_ID = "{http://www.omg.org/XMI}id"


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


@dataclass
class SofaPayload:
    """
    One sofa's raw payload, lifted out of the XMI before cassis sees it.

    The payload is kept *encoded*: `data()` decodes on demand, so a
    video that turns out to be in the store already is never decoded at
    all -- which is the whole of what "only extract it if it isn't
    there" costs at this stage.

    Sofa data arrives two ways: `sofaString` (base64 text, what the
    DUUI video components produce and what the Bundestag CAS uses) or a
    `sofaArray` reference to a ByteArray of signed bytes. Both are
    handled; anything else carries no payload and is not listed at all.
    """

    sofa_id: str
    mime: str
    encoded: str = None
    byte_array: str = None
    # The elements this payload came from, so it can be blanked in
    # place. Excluded from repr/eq: they are plumbing, and printing a
    # 169 MB attribute by accident is exactly the kind of thing this
    # module exists to avoid.
    element: object = field(default=None, repr=False, compare=False)
    array_element: object = field(default=None, repr=False, compare=False)

    def data(self):
        """The decoded bytes, or None if the payload is empty."""
        if self.encoded:
            # `validate=False`: the payload is machine-generated base64,
            # but pipelines sometimes wrap it in whitespace/newlines,
            # which strict validation would reject outright.
            return base64.b64decode(self.encoded, validate=False)

        if self.byte_array:
            # UIMA ByteArrays are signed; XMI writes them as a
            # space-separated list of -128..127.
            values = (int(value) for value in self.byte_array.split())
            return bytes(bytearray((value + 256) % 256 for value in values))

        return None


def find_media_sofas(tree):
    """
    Every sofa in `tree` that carries a payload.

    One walk: the same pass indexes xmi:id so a `sofaArray` reference
    can be resolved without a second one.
    """
    elements_by_id = {}
    sofa_elements = []

    for element in tree.iter():
        xmi_id = element.get(_XMI_ID)
        if xmi_id is not None:
            elements_by_id[xmi_id] = element
        if isinstance(element.tag, str) and etree.QName(element).localname == "Sofa":
            sofa_elements.append(element)

    payloads = []
    for element in sofa_elements:
        encoded = element.get("sofaString")
        array_element = elements_by_id.get(element.get("sofaArray"))
        byte_array = array_element.get("elements") if array_element is not None else None
        if not encoded and not byte_array:
            continue
        payloads.append(
            SofaPayload(
                sofa_id=element.get("sofaID") or "?",
                mime=element.get("mimeType") or "",
                encoded=encoded,
                byte_array=byte_array,
                element=element,
                array_element=array_element,
            )
        )
    return payloads


def read_video_filename(tree):
    """
    The filename this document describes, read off the raw XML.

    Same precedence as parsers/video.py's `parse` -- MultimediaElement
    first, DocumentMetaData second -- because it answers the same
    question, only earlier: pipeline.py needs the name *before* the CAS
    is loaded, to decide whether this video is already imported without
    paying for a cassis parse it may be about to throw away. Returns
    None if neither annotation is present, in which case the caller
    falls back to reading it from the loaded CAS.
    """
    metadata = None

    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue
        localname = etree.QName(element).localname
        if localname == "MultimediaElement":
            filename = element.get("filename")
            if filename:
                return filename
        elif localname == "DocumentMetaData" and metadata is None:
            metadata = element.get("documentTitle")

    return metadata


def select_video_sofa(sofas):
    """
    The sofa holding the video, or None if there is none.

    DUUI_VIDEO_VIEW (default `_InitialView`) names the view to read.
    Any other `video/*` sofa is used as a fallback, so a pipeline that
    routes the video somewhere unexpected still works without
    configuration -- the setting only has to be reached for when the
    CAS has several video sofas, or the intended one isn't labelled
    `video/*` at all.
    """
    configured = None
    fallback = None

    for sofa in sofas:
        if sofa.sofa_id == VIDEO_VIEW:
            configured = sofa
        elif fallback is None and sofa.mime.startswith("video/"):
            fallback = sofa

    if configured is not None:
        if not configured.mime or configured.mime.startswith("video/"):
            return configured
        # Named view holds something, but it is audio or text --
        # writing that out as a video would produce an unplayable
        # file, so say why it was skipped rather than doing it.
        print(
            f"[importer] warning: DUUI_VIDEO_VIEW='{VIDEO_VIEW}' is a "
            f"'{configured.mime}' sofa, not a video -- ignoring it"
        )
    elif VIDEO_VIEW != _DEFAULT_VIDEO_VIEW:
        # Only worth flagging when explicitly configured: the default
        # view is simply absent from plenty of CAS files.
        print(
            f"[importer] warning: DUUI_VIDEO_VIEW='{VIDEO_VIEW}' is not a "
            f"view in this CAS"
        )

    return fallback


def strip_media_sofas(sofas, video=None):
    """
    Blank the media payloads in the tree these sofas came from, in
    place. Returns the sofa ids blanked, for logging.

    What gets blanked, and why not simply "everything":

      - the sofa `video` (whatever DUUI_VIDEO_VIEW's lookup chose),
        always. Its bytes have already been captured, and it is the one
        that makes the file unloadable.
      - any sofa whose MIME says it is not text (`audio/*`, further
        `video/*`, anything else). Costs nothing extra -- it is the
        same walk -- and covers a pipeline that embeds something large
        besides the video.

    Text sofas are left alone: annotations on them are offset-based
    (`begin`/`end` index into the sofa string), so blanking one would
    silently invalidate every annotation over it. A sofa with no MIME
    at all is treated as possibly-text for the same reason.
    """
    stripped = []
    for sofa in sofas:
        selected = video is not None and sofa is video
        if not selected and (not sofa.mime or sofa.mime.startswith("text/")):
            continue

        if sofa.element is not None and sofa.encoded is not None:
            sofa.element.set("sofaString", "")
        if sofa.array_element is not None:
            sofa.array_element.set("elements", "")
        stripped.append(sofa.sofa_id)
    return stripped


def cas_source(tree):
    """The tree as a byte stream, ready for load_cas_from_xmi()."""
    buffer = BytesIO()
    tree.write(buffer, encoding="UTF-8", xml_declaration=True)
    buffer.seek(0)
    return buffer


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
