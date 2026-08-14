"""
Tests for the agent-result -> playable-clip conversion in
src/backend/routes/ask.py.

This is what decides whether the Ask panel shows a clickable segment
list or falls back to a plain table, so it runs on every answered
question. Pure function over the agent's already-executed result --
no database and no LLM involved.
"""

from backend.routes.ask import _playable_segments


def test_no_segments_when_the_result_has_no_time_columns():
    result = {"columns": ["video_id", "n"], "rows": [{"video_id": 1, "n": 3}]}
    assert _playable_segments(result) == []


def test_no_segments_when_video_id_is_missing():
    result = {
        "columns": ["start_time", "end_time"],
        "rows": [{"start_time": 1.0, "end_time": 2.0}],
    }
    assert _playable_segments(result) == []


def test_builds_a_segment_and_keeps_the_rest_of_the_row_as_meta():
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


def test_skips_rows_with_a_null_video_id_or_start_time():
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


def test_null_end_time_collapses_to_a_zero_length_clip():
    # An instant (a single frame's emotion reading, say) has no end --
    # the frontend still needs somewhere to seek to.
    result = {
        "columns": ["video_id", "start_time", "end_time"],
        "rows": [{"video_id": 1, "start_time": 7.25, "end_time": None}],
    }
    assert _playable_segments(result)[0]["end_time"] == 7.25


def test_empty_rows_give_no_segments():
    result = {"columns": ["video_id", "start_time", "end_time"], "rows": []}
    assert _playable_segments(result) == []
