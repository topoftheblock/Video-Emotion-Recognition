"""Tests for duui_parser/pipeline.py's batch path resolution -- pure
path logic, no DB or CAS parsing involved."""

from duui_parser.pipeline import resolve_xmi_paths


def test_directory_expands_to_its_xmi_files(tmp_path):
    (tmp_path / "b.xmi").touch()
    (tmp_path / "a.xmi").touch()
    (tmp_path / "video.mp4").touch()          # companion video, not an input
    (tmp_path / "notes.txt").touch()

    result = resolve_xmi_paths([tmp_path])

    assert [p.name for p in result] == ["a.xmi", "b.xmi"]  # sorted, .xmi only


def test_directory_is_not_recursive(tmp_path):
    (tmp_path / "top.xmi").touch()
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "deep.xmi").touch()

    result = resolve_xmi_paths([tmp_path])

    assert [p.name for p in result] == ["top.xmi"]


def test_explicit_file_is_taken_as_is(tmp_path):
    odd = tmp_path / "export.cas"
    odd.touch()

    assert resolve_xmi_paths([odd]) == [odd]


def test_mix_of_files_and_directories(tmp_path):
    loose = tmp_path / "loose.xmi"
    loose.touch()
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "inner.xmi").touch()

    result = resolve_xmi_paths([loose, folder])

    assert [p.name for p in result] == ["loose.xmi", "inner.xmi"]


def test_deduplicates_same_file_named_twice(tmp_path):
    target = tmp_path / "dup.xmi"
    target.touch()

    # Named directly AND picked up via its directory -- must import once.
    result = resolve_xmi_paths([target, tmp_path])

    assert result == [target]


def test_empty_directory_yields_nothing(tmp_path):
    assert resolve_xmi_paths([tmp_path]) == []
