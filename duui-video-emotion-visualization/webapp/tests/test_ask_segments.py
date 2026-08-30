"""Tests turning an agent result into spans the frontend can play.

This decides whether the Ask panel shows a clickable list or falls back
to a plain table, so it runs on every answered question. A pure
function over the already-executed result: no database, no model.
"""

from backend.routes.ask import _playable_segments


def test_no_segments_when_the_result_has_no_time_columns() -> None:
    """Without the time columns there is nothing to seek to."""
    result = {"columns": ["video_id", "n"], "rows": [{"video_id": 1, "n": 3}]}
    assert _playable_segments(result) == []


def test_no_segments_when_video_id_is_missing() -> None:
    """A time without a video cannot be played either."""
    result = {
        "columns": ["start_time", "end_time"],
        "rows": [{"start_time": 1.0, "end_time": 2.0}],
    }
    assert _playable_segments(result) == []


def test_builds_a_segment_and_keeps_the_rest_of_the_row_as_meta() -> None:
    """Everything not part of the span rides along for display."""
    result = {
        "columns": ["video_id", "start_time", "end_time", "dominant_label"],
        "rows": [
            {
                "video_id": 2,
                "start_time": 1.5,
                "end_time": 3.0,
                "dominant_label": "anger",
            }
        ],
    }
    assert _playable_segments(result) == [
        {
            "video_id": 2,
            "start_time": 1.5,
            "end_time": 3.0,
            "meta": {"dominant_label": "anger"},
        }
    ]


def test_skips_rows_with_a_null_video_id_or_start_time() -> None:
    """An unplayable row is dropped, and the rest still come through."""
    result = {
        "columns": ["video_id", "start_time", "end_time"],
        "rows": [
            {"video_id": None, "start_time": 1.0, "end_time": 2.0},
            {"video_id": 1, "start_time": None, "end_time": 2.0},
            {"video_id": 1, "start_time": 4.0, "end_time": 5.0},
        ],
    }
    segments = _playable_segments(result)
    assert [s["start_time"] for s in segments] == [4.0]


def test_null_end_time_collapses_to_a_zero_length_span() -> None:
    """A moment with no extent is still somewhere to seek to.

    A single frame's emotion reading has no end, and dropping it would
    lose a result the question asked for.
    """
    result = {
        "columns": ["video_id", "start_time", "end_time"],
        "rows": [{"video_id": 1, "start_time": 7.25, "end_time": None}],
    }
    assert _playable_segments(result)[0]["end_time"] == 7.25


def test_empty_rows_give_no_segments() -> None:
    """A result with the right columns but no rows yields nothing."""
    result = {"columns": ["video_id", "start_time", "end_time"], "rows": []}
    assert _playable_segments(result) == []
