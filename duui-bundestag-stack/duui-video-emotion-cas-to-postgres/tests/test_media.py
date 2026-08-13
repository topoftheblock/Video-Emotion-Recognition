"""Tests for src/main/media.py -- pure filesystem logic, no DB
needed. Covers the behavior the Docker "importer places the video"
flow depends on: idempotent copy, extraction of a video embedded in
the CAS when no companion file exists, and graceful (non-raising)
handling of a missing source or filename."""

import base64
from types import SimpleNamespace

from main import media


def _sofa(sofa_id, mime=None, data=None):
    """One sofa, shaped like the cassis object media.py reads."""
    return SimpleNamespace(
        sofaID=sofa_id,
        mimeType=mime,
        sofaString=base64.b64encode(data).decode("ascii") if data is not None else None,
    )


def _cas(*sofas):
    """A stand-in for a loaded CAS (cas.views -> view.sofa)."""
    return SimpleNamespace(views=[SimpleNamespace(sofa=s) for s in sofas])


def _cas_with_video_sofa(data, mime="video/mp4", sofa_id="_InitialView"):
    """The common case: a CAS whose video sits on one base64 sofa."""
    return _cas(_sofa(sofa_id, mime, data))


def test_place_video_file_copies_when_missing(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    (source_dir / "clip.mp4").write_bytes(b"fake video bytes")
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = media.place_video_file("clip.mp4", source_dir)

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"fake video bytes"


def test_place_video_file_is_idempotent(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    (source_dir / "clip.mp4").write_bytes(b"original")
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))

    media.place_video_file("clip.mp4", source_dir)
    # Change the source after the first placement -- a rerun must NOT
    # overwrite the already-placed file (matches the "already present,
    # leaving as-is" log line rather than silently re-copying).
    (source_dir / "clip.mp4").write_bytes(b"changed")
    result = media.place_video_file("clip.mp4", source_dir)

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"original"
    assert "already present" in capsys.readouterr().out


def test_place_video_file_missing_source_returns_none(tmp_path, monkeypatch, capsys):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))

    result = media.place_video_file("missing.mp4", source_dir)

    assert result is None
    assert not (dest_dir / "missing.mp4").exists()
    assert "warning" in capsys.readouterr().out.lower()


def test_place_video_file_no_filename_returns_none(tmp_path, monkeypatch):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))

    assert media.place_video_file(None, tmp_path) is None
    assert media.place_video_file("", tmp_path) is None
    assert media.place_video_file("unknown", tmp_path) is None


def test_extract_video_from_cas_writes_sofa_bytes(tmp_path, monkeypatch):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    cas = _cas_with_video_sofa(b"fake mp4 bytes")

    result = media.extract_video_from_cas(cas, "clip.mp4")

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"fake mp4 bytes"


def test_extract_video_from_cas_ignores_non_video_sofas(tmp_path, monkeypatch):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    # A transcript-only CAS (the shipped demo looks like this): an empty
    # _InitialView plus a text sofa, no video payload to recover.
    cas = _cas(_sofa("_InitialView"), _sofa("transcriptView", "text/plain", b"Vielen Dank."))

    assert media.extract_video_from_cas(cas, "clip.mp4") is None
    assert not dest_dir.exists() or not (dest_dir / "clip.mp4").exists()


def test_video_view_selects_the_configured_sofa(tmp_path, monkeypatch):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    monkeypatch.setattr(media, "VIDEO_VIEW", "videoView")
    # Two video sofas: DUUI_VIDEO_VIEW decides which one is the video,
    # rather than "whichever came first".
    cas = _cas(
        _sofa("_InitialView", "video/mp4", b"wrong one"),
        _sofa("videoView", "video/mp4", b"the configured one"),
    )

    media.extract_video_from_cas(cas, "clip.mp4")

    assert (dest_dir / "clip.mp4").read_bytes() == b"the configured one"


def test_video_view_defaults_to_initial_view(tmp_path, monkeypatch):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    monkeypatch.setattr(media, "VIDEO_VIEW", "_InitialView")
    cas = _cas(
        _sofa("_InitialView", "video/mp4", b"initial view video"),
        _sofa("otherVideoView", "video/mp4", b"other"),
    )

    media.extract_video_from_cas(cas, "clip.mp4")

    assert (dest_dir / "clip.mp4").read_bytes() == b"initial view video"


def test_video_view_falls_back_to_any_video_sofa(tmp_path, monkeypatch, capsys):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    monkeypatch.setattr(media, "VIDEO_VIEW", "typoView")
    cas = _cas(_sofa("videoView", "video/mp4", b"found anyway"))

    result = media.extract_video_from_cas(cas, "clip.mp4")

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"found anyway"
    assert "not a view in this CAS" in capsys.readouterr().out


def test_video_view_pointing_at_audio_is_refused(tmp_path, monkeypatch, capsys):
    dest_dir = tmp_path / "dest"
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    monkeypatch.setattr(media, "VIDEO_VIEW", "audioView")
    # Writing an mp3 out as the "video" would just produce an unplayable
    # file under a .mp4 name -- refuse instead.
    cas = _cas(_sofa("audioView", "audio/mp3", b"id3 audio bytes"))

    assert media.extract_video_from_cas(cas, "clip.mp4") is None
    assert "not a video" in capsys.readouterr().out


def test_ensure_video_available_prefers_the_file_on_disk(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    (source_dir / "clip.mp4").write_bytes(b"from disk")
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    cas = _cas_with_video_sofa(b"from cas")

    result = media.ensure_video_available("clip.mp4", source_dir, cas)

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"from disk"


def test_ensure_video_available_falls_back_to_cas(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()  # deliberately empty -- no companion video file
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    cas = _cas_with_video_sofa(b"from cas")

    result = media.ensure_video_available("clip.mp4", source_dir, cas)

    assert result == dest_dir / "clip.mp4"
    assert (dest_dir / "clip.mp4").read_bytes() == b"from cas"


def test_ensure_video_available_warns_when_neither_source_has_it(
    tmp_path, monkeypatch, capsys
):
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    monkeypatch.setattr(media, "VIDEO_MEDIA_DIR", str(dest_dir))
    cas = SimpleNamespace(views=[])

    result = media.ensure_video_available("clip.mp4", source_dir, cas)

    assert result is None
    out = capsys.readouterr().out.lower()
    assert "warning" in out and "none embedded in the cas" in out
