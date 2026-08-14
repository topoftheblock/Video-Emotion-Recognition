"""
Regression tests for the two annotators that share modality='text'.

Real data carries one Ekman-mapped text emotion *and* one raw 28-class
GoEmotions text emotion per sentence (see
query_agent/schema_context.py). Both are modality='text', so anything
that treats that modality as a single series counts every sentence
twice -- which is how the insights panel came to report a label more
often than the video had sentences.

Needs a live Postgres with the schema applied: the fixture writes a
throwaway video and deletes it again (base_emotions is ON DELETE
CASCADE), because `backend.db.query` opens its own connection per call
and so cannot see an uncommitted transaction.
"""

import psycopg2
import pytest

from backend.config import DB_CONFIG
from backend.queries import stats, videos


def _next_id(cur, table, column):
    """
    An id above everything already in `table`.

    The importer writes primary keys straight from the CAS's own xmi:id
    space rather than letting the BIGSERIAL assign them, so on a
    database that has had a real import the sequences trail the actual
    maximum and nextval() hands back an id that is already taken.
    """
    cur.execute(f"SELECT COALESCE(max({column}), 0) + 1 FROM {table}")
    return cur.fetchone()[0]


@pytest.fixture
def video_with_both_text_annotators(db_available):
    """One sentence, read by both text annotators -- the shape that
    used to double-count."""
    if not db_available:
        pytest.skip("no DB reachable")

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    with conn.cursor() as cur:
        video_id = _next_id(cur, "videos", "video_id")
        cur.execute(
            "INSERT INTO videos (video_id, filename) "
            "VALUES (%s, 'pytest-emotion-series.mp4')",
            (video_id,),
        )
        emotion_id = _next_id(cur, "base_emotions", "emotion_id")
        cur.execute(
            """
            INSERT INTO base_emotions
                (emotion_id, video_id, modality, granularity, start_time, end_time,
                 begin_offset, end_offset, dominant_label)
            VALUES
                -- Ekman-mapped: on the timeline.
                (%(e1)s, %(v)s, 'text', 'sentence', 0.0, 1.0, 0, 10, 'neutral'),
                -- Raw GoEmotions: the same sentence, character offsets only.
                (%(e2)s, %(v)s, 'text', 'sentence', NULL, NULL, 0, 10, 'neutral')
            """,
            {"v": video_id, "e1": emotion_id, "e2": emotion_id + 1},
        )
    try:
        yield video_id
    finally:
        # base_emotions is ON DELETE CASCADE from videos.
        with conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE video_id = %s", (video_id,))
        conn.close()


def test_the_two_text_annotators_are_counted_as_separate_series(
    video_with_both_text_annotators,
):
    rows = stats.emotion_distribution(video_with_both_text_annotators)

    # One 'neutral' each, not a single row of n=2 for a one-sentence video.
    assert [(r["series"], r["dominant_label"], r["n"]) for r in rows] == [
        ("text", "neutral", 1),
        ("text (raw GoEmotions)", "neutral", 1),
    ]
    # The modality both series came from is still reported, so a caller
    # that wants them merged can do it deliberately.
    assert {r["modality"] for r in rows} == {"text"}


def test_the_playback_payload_carries_only_readings_on_the_timeline(
    video_with_both_text_annotators,
):
    payload = videos.build_playback_payload(video_with_both_text_annotators)

    # The frontend renders everything off currentTime, so a reading
    # with no time cannot be placed -- and leaving it in is what would
    # let a panel average two different label vocabularies together.
    text_emotions = payload["emotions"]["text"]
    assert len(text_emotions) == 1
    assert text_emotions[0]["start_time"] == 0.0
