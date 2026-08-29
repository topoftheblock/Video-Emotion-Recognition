"""The raw XMI side of media: finding, reading and removing sofas.

Works on the lxml tree *before* cassis parses it, which is the point: a
CAS carrying an embedded video is too large to load with the video still
in it, so the media sofas are read and stripped at the XML level first.

The filesystem half — putting a video where the webapp can serve it — is
in `video_files.py`.
"""

import base64
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from lxml import etree

from ..config import VIDEO_VIEW

# What DUUI_VIDEO_VIEW falls back to when unset. Knowing whether the
# view name was chosen or inherited decides whether "no such view in
# this CAS" is worth warning about.
_DEFAULT_VIDEO_VIEW = "_InitialView"

# XMI ids are namespaced. `sofaArray` refers to a ByteArray element
# carried elsewhere in the document, so resolving it means a lookup by
# that id.
_XMI_ID = "{http://www.omg.org/XMI}id"


@dataclass
class SofaPayload:
    """One sofa's payload, lifted out of the XML before cassis sees it.

    The payload is kept *encoded*: `data()` decodes on demand, so a
    video that turns out to be in the store already is never decoded at
    all. That is the whole cost of "only extract it if it is missing".

    Sofa data arrives two ways: `sofaString`, base64 text, which is what
    the DUUI video components produce; or a `sofaArray` reference to a
    ByteArray of signed bytes. Both are handled. Anything else carries
    no payload and is not listed at all.
    """

    sofa_id: str
    mime: str
    encoded: str | None = None
    byte_array: str | None = None
    # The elements this payload came from, so it can be blanked in
    # place. Excluded from repr and eq: they are plumbing, and printing
    # a video-sized attribute by accident is exactly what this module
    # exists to avoid.
    element: Any = field(default=None, repr=False, compare=False)
    array_element: Any = field(default=None, repr=False, compare=False)

    def data(self) -> bytes | None:
        """Return the decoded bytes, or None if the payload is empty."""
        if self.encoded:
            # `validate=False`: the payload is machine-generated base64,
            # but pipelines sometimes wrap it in newlines, which strict
            # validation would reject outright.
            return base64.b64decode(self.encoded, validate=False)

        if self.byte_array:
            # UIMA ByteArrays are signed; XMI writes them as a
            # space-separated list of -128..127.
            values = (int(value) for value in self.byte_array.split())
            return bytes(bytearray((value + 256) % 256 for value in values))

        return None


def find_media_sofas(tree: Any) -> list[SofaPayload]:
    """Return every sofa in `tree` that carries a payload.

    One walk does it: the same pass indexes `xmi:id`, so a `sofaArray`
    reference can be resolved without a second one.

    Args:
        tree: The parsed lxml tree of the CAS.

    Returns:
        A payload per sofa that has one, in document order.
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
        byte_array = (
            array_element.get("elements") if array_element is not None else None
        )
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


def read_video_filename(tree: Any) -> str | None:
    """Read the filename this document describes, off the raw XML.

    Same precedence as `parsers/video.py` — MultimediaElement first,
    DocumentMetaData second — because it answers the same question, only
    earlier: `pipeline.py` needs the name *before* the CAS is loaded, so
    it can tell whether this video is already imported without paying
    for a cassis parse it may be about to throw away.

    Args:
        tree: The parsed lxml tree of the CAS.

    Returns:
        The filename, or None if neither annotation carries one, in
        which case the caller reads it from the loaded CAS instead.
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


def select_video_sofa(sofas: list[SofaPayload]) -> SofaPayload | None:
    """Return the sofa holding the video, or None if there is none.

    DUUI_VIDEO_VIEW, `_InitialView` by default, names the view to read.
    Any other `video/*` sofa is used as a fallback, so a pipeline that
    routes the video somewhere unexpected still works unconfigured. The
    setting only has to be reached for when the CAS holds several video
    sofas, or the intended one is not labelled `video/*` at all.

    Args:
        sofas: The payload-carrying sofas found in the document.

    Returns:
        The chosen sofa, or None.
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
        # The named view holds something, but it is audio or text.
        # Writing that out as a video would produce an unplayable file,
        # so say why it was skipped instead of doing it.
        print(
            f"[importer] warning: DUUI_VIDEO_VIEW='{VIDEO_VIEW}' is a "
            f"'{configured.mime}' sofa, not a video — ignoring it"
        )
    elif VIDEO_VIEW != _DEFAULT_VIDEO_VIEW:
        # Only worth flagging when explicitly configured: the default
        # view is simply absent from plenty of CAS files.
        print(
            f"[importer] warning: DUUI_VIDEO_VIEW='{VIDEO_VIEW}' is not a "
            f"view in this CAS"
        )

    return fallback


def strip_media_sofas(
    sofas: list[SofaPayload], video: SofaPayload | None = None
) -> list[str]:
    """Blank these sofas' payloads in place, in their own tree.

    What gets blanked, and why not simply everything:

    - The sofa `video`, whatever DUUI_VIDEO_VIEW's lookup chose, always.
      Its bytes have already been captured, and it is the one that makes
      the file unloadable.
    - Any sofa whose MIME says it is not text: `audio/*`, further
      `video/*`, anything else. This costs nothing extra, being the same
      walk, and covers a pipeline that embeds something large besides
      the video.

    Text sofas are left alone. Annotations over them are offset-based —
    `begin` and `end` index into the sofa string — so blanking one
    would silently invalidate every annotation on it. A sofa with no
    MIME at all is treated as possibly-text for the same reason.

    Args:
        sofas: The payload-carrying sofas found in the document.
        video: The sofa chosen as the video, if one was.

    Returns:
        The ids of the sofas blanked, for logging.
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


def cas_source(tree: Any) -> BytesIO:
    """Serialize the tree to a byte stream, for `load_cas_from_xmi`."""
    buffer = BytesIO()
    tree.write(buffer, encoding="UTF-8", xml_declaration=True)
    buffer.seek(0)
    return buffer
