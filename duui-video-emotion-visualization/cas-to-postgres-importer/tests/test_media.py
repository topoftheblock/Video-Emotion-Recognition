"""Tests for `cas/sofas.py` and `video_files.py`.

Filesystem and XML logic only; no database. Covers the behaviour the
"importer places the video" flow depends on: an idempotent copy,
extraction of a video embedded in the CAS when no companion file
exists, and handling a missing source or filename without raising.

Because the media payloads are read off the raw XML before cassis sees
them, the fixtures here build real XML rather than a stand-in for a
loaded CAS. That is also what lets them assert the other half of the
contract: the document handed to cassis keeps every annotation and
every text sofa, and loses only the media bytes.
"""

import base64
from pathlib import Path

import pytest
from lxml import etree
from lxml.etree import _ElementTree

from importer import video_files
from importer.cas import sofas

XMI_ID = "{http://www.omg.org/XMI}id"


def _xmi(*sofas: tuple, extra: str = "") -> _ElementTree:
    """Build a CAS document carrying the given sofas.

    Args:
        *sofas: One `(sofaID, mimeType, payload or None)` per sofa.
        extra: Raw XML to insert after the sofas.

    Returns:
        The parsed tree. Its namespaces and trailing View element
        mirror what the pipelines emit, since the code under test
        reads both.
    """
    parts = []
    for index, (sofa_id, mime, data) in enumerate(sofas, start=1):
        attrs = f'xmi:id="{index}" sofaNum="{index}" sofaID="{sofa_id}"'
        if mime:
            attrs += f' mimeType="{mime}"'
        if data is not None:
            attrs += f' sofaString="{base64.b64encode(data).decode("ascii")}"'
        parts.append(f"<cas:Sofa {attrs}/>")
    return etree.fromstring(
        '<xmi:XMI xmlns:xmi="http://www.omg.org/XMI" '
        'xmlns:cas="http:///uima/cas.ecore" '
        'xmlns:tcas="http:///uima/tcas.ecore" xmi:version="2.0">'
        f"{''.join(parts)}{extra}"
        '<cas:View sofa="1" members="99"/>'
        "</xmi:XMI>".encode("utf-8")
    ).getroottree()


def _video_xmi(
    data: bytes, mime: str = "video/mp4", sofa_id: str = "_InitialView"
) -> _ElementTree:
    """Build the common case: one video, on one base64 sofa."""
    return _xmi((sofa_id, mime, data))


def _payload(tree: _ElementTree) -> sofas.SofaPayload:
    """Return the sofa the code under test treats as the video.

    Asserts one was found: every caller here builds a tree that has
    one, and the "no video sofa" case is tested through
    `select_video_sofa` directly.
    """
    found = sofas.select_video_sofa(sofas.find_media_sofas(tree))
    assert found is not None
    return found


def test_place_video_file_copies_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A video not yet in the store is copied into it."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    (source_dir / "clip.mp4").write_bytes(b"fake video bytes")
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = video_files.place_video_file("clip.mp4", source_dir)

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"fake video bytes"


def test_place_video_file_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A second run leaves the already-placed file untouched."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    (source_dir / "clip.mp4").write_bytes(b"original")
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    video_files.place_video_file("clip.mp4", source_dir)
    # Change the source after the first placement: a rerun must not
    # overwrite what is already there.
    (source_dir / "clip.mp4").write_bytes(b"changed")
    result = video_files.place_video_file("clip.mp4", source_dir)

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"original"
    assert "already present" in capsys.readouterr().out


def test_place_video_file_missing_source_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A missing source warns and returns None, rather than raising."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = video_files.place_video_file("missing.mp4", source_dir)

    assert result is None
    assert not (dest_dir / "missing.mp4").exists()
    assert "warning" in capsys.readouterr().out.lower()


def test_place_video_file_no_filename_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No usable filename means there is nothing to place."""
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    assert video_files.place_video_file(None, tmp_path) is None
    assert video_files.place_video_file("", tmp_path) is None
    assert video_files.place_video_file("unknown", tmp_path) is None


def test_extract_video_payload_writes_sofa_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A base64 sofa is decoded into the video store."""
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = video_files.extract_video_payload(
        _payload(_video_xmi(b"fake mp4 bytes")), "clip.mp4"
    )

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"fake mp4 bytes"


def test_extract_video_payload_reads_a_sofa_byte_array(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other payload form, a signed ByteArray, decodes too."""
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))
    # Signed bytes rather than base64 text: 0xFF arrives as -1.
    tree = _xmi(
        ("_InitialView", "video/mp4", None),
        extra='<cas:ByteArray xmi:id="7" elements="0 1 -1 127"/>',
    )
    for element in tree.iter():
        if element.get("sofaID") == "_InitialView":
            element.set("sofaArray", "7")

    result = video_files.extract_video_payload(_payload(tree), "clip.mp4")

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == bytes([0, 1, 255, 127])


def test_no_video_sofa_means_nothing_to_extract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CAS with no video payload yields nothing to write."""
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))
    # A transcript-only CAS: an empty _InitialView plus a text sofa.
    tree = _xmi(
        ("_InitialView", None, None), ("transcriptView", "text/plain", b"Vielen Dank.")
    )

    payload = sofas.select_video_sofa(sofas.find_media_sofas(tree))
    assert payload is None
    assert video_files.extract_video_payload(payload, "clip.mp4") is None
    assert not dest_dir.exists() or not (dest_dir / "clip.mp4").exists()


def test_video_view_selects_the_configured_sofa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With two video sofas, the configured view decides."""
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "videoView")
    # Not "whichever came first".
    tree = _xmi(
        ("_InitialView", "video/mp4", b"wrong one"),
        ("videoView", "video/mp4", b"the configured one"),
    )

    assert _payload(tree).data() == b"the configured one"


def test_video_view_defaults_to_initial_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unconfigured, the default view is the one that is read."""
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "_InitialView")
    tree = _xmi(
        ("_InitialView", "video/mp4", b"initial view video"),
        ("otherVideoView", "video/mp4", b"other"),
    )

    assert _payload(tree).data() == b"initial view video"


def test_video_view_falls_back_to_any_video_sofa(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A named view that is absent falls back, and says so."""
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "typoView")
    tree = _xmi(("videoView", "video/mp4", b"found anyway"))

    assert _payload(tree).data() == b"found anyway"
    assert "not a view in this CAS" in capsys.readouterr().out


def test_video_view_pointing_at_audio_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A view holding audio is refused rather than written out.

    Writing it as the video would produce an unplayable file under a
    video's name.
    """
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "audioView")
    tree = _xmi(("audioView", "audio/mp3", b"id3 audio bytes"))

    assert sofas.select_video_sofa(sofas.find_media_sofas(tree)) is None
    assert "not a video" in capsys.readouterr().out


def test_stripping_removes_media_payloads_but_keeps_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Media payloads are blanked; text sofas survive intact."""
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "_InitialView")
    tree = _xmi(
        ("_InitialView", "video/mp4", b"a video"),
        ("audioView", "audio/mp3", b"some audio"),
        ("transcriptView", "text/plain", b"Vielen Dank."),
    )
    found = sofas.find_media_sofas(tree)

    stripped = sofas.strip_media_sofas(found, video=sofas.select_video_sofa(found))

    assert set(stripped) == {"_InitialView", "audioView"}
    remaining = {
        element.get("sofaID"): element.get("sofaString")
        for element in tree.iter()
        if element.get("sofaID")
    }
    assert remaining["_InitialView"] == ""
    assert remaining["audioView"] == ""
    # Text sofas carry offset-based annotations: blanking one would
    # invalidate every annotation over it.
    assert base64.b64decode(remaining["transcriptView"]) == b"Vielen Dank."


def test_stripping_leaves_a_sofa_with_no_mime_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unlabelled sofa is left alone, in case it is text.

    The cost of being wrong is silently broken offsets.
    """
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "videoView")
    tree = _xmi(("mysteryView", None, b"could be anything"))
    found = sofas.find_media_sofas(tree)

    assert sofas.strip_media_sofas(found, video=sofas.select_video_sofa(found)) == []


def test_stripping_keeps_the_payload_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The captured payload still decodes after the tree is blanked."""
    monkeypatch.setattr(sofas, "VIDEO_VIEW", "_InitialView")
    tree = _xmi(("_InitialView", "video/mp4", b"a video"))
    found = sofas.find_media_sofas(tree)
    payload = sofas.select_video_sofa(found)
    assert payload is not None

    sofas.strip_media_sofas(found, video=payload)

    # The whole ordering the import depends on: captured before the
    # blanking, still extractable afterwards.
    assert payload.data() == b"a video"
    assert b'sofaString=""' in etree.tostring(tree)


def test_cas_source_is_a_readable_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """The serialized tree comes back as a readable stream."""
    tree = _xmi(("transcriptView", "text/plain", b"Vielen Dank."))

    source = sofas.cas_source(tree)

    assert b"transcriptView" in source.read()


def test_ensure_video_available_prefers_the_file_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A companion file on disk wins over the embedded copy."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    (source_dir / "clip.mp4").write_bytes(b"from disk")
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = video_files.ensure_video_available(
        "clip.mp4", source_dir, _payload(_video_xmi(b"from cas"))
    )

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"from disk"


def test_ensure_video_available_falls_back_to_the_sofa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no file on disk, the embedded copy is used."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()  # deliberately empty: no companion video file
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = video_files.ensure_video_available(
        "clip.mp4", source_dir, _payload(_video_xmi(b"from cas"))
    )

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"from cas"


def test_ensure_video_available_does_not_decode_an_already_placed_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A video already in the store is never decoded again."""
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "clip.mp4").write_bytes(b"already here")
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    # Decoding a video already in the store is exactly the work this
    # ordering exists to skip. Reaching data() at all fails the test.
    payload = _payload(_video_xmi(b"from cas"))

    def _fail() -> bytes:
        """Stand in for `data()`, failing if anything calls it."""
        raise AssertionError("payload was decoded")

    payload.data = _fail  # type: ignore[method-assign]

    result = video_files.ensure_video_available(
        "clip.mp4", tmp_path / "source", payload
    )

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"already here"


def test_ensure_video_available_warns_when_neither_source_has_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """With neither source, rows still stand and a warning explains."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    monkeypatch.setattr(video_files, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = video_files.ensure_video_available("clip.mp4", source_dir, None)

    assert result is None
    # Anchored on what the message must convey — the filename, and
    # where to put the file — rather than on its exact phrasing.
    out = capsys.readouterr().out
    assert "clip.mp4" in out
    assert str(dest_dir) in out
