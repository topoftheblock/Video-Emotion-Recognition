"""Tests for duui_parser/media.py -- pure filesystem logic, no DB
needed. Covers the behavior the Docker "importer places the video"
flow depends on: idempotent copy, and graceful (non-raising) handling
of a missing source or filename."""

from duui_parser import media


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
