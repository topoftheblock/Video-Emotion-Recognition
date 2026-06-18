import os
import base64
import sys
from lxml import etree

XMI_PATH = "../resources/audioWav.xmi"   # adjust if needed
VIEW_NAME = "audioView"
OUT_DIR = "../output"
OUT_STEM = "test"                        # output written as test.<detected_ext>

CAS_NS = "{http:///uima/cas.ecore}"


def detect_audio_format(data: bytes) -> str:
    """Return a file extension based on the magic bytes of the audio data."""
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
    # MP3: either an ID3 tag or an MPEG audio frame sync
    if data[:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    return "bin"                               # unknown -> raw bytes


def main():
    parser = etree.XMLParser(huge_tree=True)
    tree = etree.parse(XMI_PATH, parser)
    root = tree.getroot()

    audio_b64 = None
    found_names = []
    for sofa in root.iter(f"{CAS_NS}Sofa"):
        name = sofa.get("sofaID")
        found_names.append(name)
        if name == VIEW_NAME:
            audio_b64 = sofa.get("sofaString")
            break

    if audio_b64 is None:
        print(f"View '{VIEW_NAME}' not found. Sofas present: {found_names}")
        sys.exit(1)

    data = base64.b64decode(audio_b64)
    ext = detect_audio_format(data)

    if not os.path.exists(OUT_DIR): os.mkdir(OUT_DIR)

    out_path = f"{OUT_DIR}/{OUT_STEM}.{ext}"

    with open(out_path, "wb") as f:
        f.write(data)

    print(f"Detected format: {ext}")
    print(f"Wrote {len(data)} bytes to {out_path}")
    if ext == "bin":
        print("Warning: format not recognized from magic bytes; "
              "inspect the file manually or check the pipeline output_format.")


if __name__ == "__main__":
    main()