"""
Test utility: extract and decode the audio Sofa from a DUUI XMI file.

After running the audio-extraction pipeline, the extracted audio lives inside the
output XMI as the base64 `sofaString` of the audio view. This script pulls that
string out, base64-decodes it back to raw bytes, auto-detects the audio format
from the file's magic bytes, and writes it to disk with the correct extension so
it can be played directly (no ffmpeg conversion needed).

It deliberately avoids the cassis CAS loader: the audio Sofa is a very large
single-line base64 blob that trips cassis/lxml's default buffer limit, and the
XMI also references DKPro types we don't have a typesystem for here. Parsing the
XMI directly with lxml (with huge_tree enabled) sidesteps both problems, since we
only need one attribute, not the full CAS object graph.

Adjust XMI_PATH / VIEW_NAME / OUT_DIR below to match your setup.

Author: Nickolas Eickmann
"""

import os
import base64
import sys
from lxml import etree

XMI_PATH = "../resources/audioWav.xmi"   # path to the XMI written by the pipeline
VIEW_NAME = "audioView"                  # the view whose Sofa holds the audio
OUT_DIR = "../output"                    # directory the decoded file is written to
OUT_STEM = "test"                        # output written as test.<detected_ext>

# UIMA CAS namespace, used to find <cas:Sofa> elements. Note the three slashes;
# this is the standard XMI namespace for CAS, not a typo.
CAS_NS = "{http:///uima/cas.ecore}"


def detect_audio_format(data: bytes) -> str:
    """Return a file extension guessed from the leading magic bytes of `data`.

    Each audio container starts with a recognizable signature; we match on those
    rather than trusting any external format hint. Returns "bin" if nothing
    matches, so the caller can flag an unrecognized payload.
    """
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"\x1aE\xdf\xa3":          # EBML -> Matroska/WebM (audio in webm)
        return "webm"
    if data[:4] in (b"ftyp", data[4:8]) and data[4:8] == b"ftyp":
        return "m4a"                           # MP4/M4A container
    # MP3 has no container signature; identify it either by a leading ID3 tag
    # or by an MPEG audio frame sync (0xFF followed by three set sync bits).
    if data[:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    return "bin"                               # unknown -> write raw bytes


def main():
    # huge_tree=True lifts lxml's text-node size limit so the large base64 Sofa
    # string can be parsed without "Buffer size limit exceeded".
    parser = etree.XMLParser(huge_tree=True)
    tree = etree.parse(XMI_PATH, parser)
    root = tree.getroot()

    # Scan every Sofa element and grab the base64 string of the view.
    # We also collect all Sofa names so we can report them if the view is missing.
    audio_b64 = None
    found_names = []
    for sofa in root.iter(f"{CAS_NS}Sofa"):
        name = sofa.get("sofaID")
        found_names.append(name)
        if name == VIEW_NAME:
            audio_b64 = sofa.get("sofaString")
            break

    if audio_b64 is None:
        # The view name didn't match; show what's actually present so the user
        # can correct VIEW_NAME above.
        print(f"View '{VIEW_NAME}' not found. Sofas present: {found_names}")
        sys.exit(1)

    # Decode base64 -> raw audio bytes, detect the format, and name the file.
    data = base64.b64decode(audio_b64)
    ext = detect_audio_format(data)

    if not os.path.exists(OUT_DIR):
        os.mkdir(OUT_DIR)
    out_path = f"{OUT_DIR}/{OUT_STEM}.{ext}"

    with open(out_path, "wb") as f:
        f.write(data)

    print(f"Detected format: {ext}")
    print(f"Wrote {len(data)} bytes to {out_path}")
    if ext == "bin":
        # Magic-byte detection failed; the bytes were still written so they can
        # be inspected manually (e.g. `xxd test.bin | head`).
        print("Warning: format not recognized from magic bytes; "
              "inspect the file manually or check the pipeline output_format.")


if __name__ == "__main__":
    main()