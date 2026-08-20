"""Tests for src/pipeline.py's batch path resolution -- pure
path logic, no DB or CAS parsing involved."""

import importlib
import os

import pytest

from main import config
from main.pipeline import describe_missing_inputs, resolve_xmi_paths


def _config_with_env(monkeypatch, **env):
    """Re-read config.py under a patched environment. Reloaded again at
    teardown so the module-level values other tests see are restored."""
    for name, value in env.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def _restore_config():
    yield
    importlib.reload(config)


def test_video_dir_defaults_to_the_xmi_dir(monkeypatch):
    """An unset DUUI_INPUT_VIDEO_DIR means "next to the .xmi files",
    not some fixed folder -- so pointing the importer at one directory
    of pipeline output takes one setting rather than two. Mirrors the
    nested default on the host-side mount in docker-compose.yml."""
    reloaded = _config_with_env(
        monkeypatch,
        DUUI_INPUT_XMI_DIR="/pipeline/output",
        DUUI_INPUT_VIDEO_DIR=None,
    )

    assert reloaded.INPUT_VIDEO_DIR == "/pipeline/output"


def test_video_dir_is_independent_when_set(monkeypatch):
    reloaded = _config_with_env(
        monkeypatch,
        DUUI_INPUT_XMI_DIR="/pipeline/xmi",
        DUUI_INPUT_VIDEO_DIR="/pipeline/videos",
    )

    assert reloaded.INPUT_XMI_DIR == "/pipeline/xmi"
    assert reloaded.INPUT_VIDEO_DIR == "/pipeline/videos"


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


# describe_missing_inputs -- the three causes that all look identical
# to resolve_xmi_paths must come back as distinguishable reasons.

def test_missing_path_is_reported_as_nonexistent(tmp_path):
    (reason,) = describe_missing_inputs([tmp_path / "nope"])

    assert "does not exist" in reason


def test_empty_directory_is_reported_as_empty(tmp_path):
    (reason,) = describe_missing_inputs([tmp_path])

    assert "is empty" in reason


def test_directory_without_xmi_lists_what_it_does_hold(tmp_path):
    (tmp_path / "video.mp4").touch()
    (tmp_path / "notes.txt").touch()

    (reason,) = describe_missing_inputs([tmp_path])

    assert "none named *.xmi" in reason
    assert "video.mp4" in reason and "notes.txt" in reason


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory permissions")
def test_unreadable_directory_is_reported_as_a_permission_problem(tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "present.xmi").touch()
    locked.chmod(0o000)
    try:
        (reason,) = describe_missing_inputs([locked])
    finally:
        locked.chmod(0o755)  # so tmp_path cleanup can remove it

    assert "cannot be read" in reason
    assert "is empty" not in reason
