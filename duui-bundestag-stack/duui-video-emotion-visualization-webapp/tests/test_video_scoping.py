"""
Tests that the viewer's queries never read across videos.

Every id that came out of a CAS -- emotion_id, person_id, segment_id --
is only unique within one video (see db/schema.sql's identity note), so
a query that filters or joins on one of them alone silently pulls in
other videos' rows. The failure mode is not an error: it is a payload
that looks right and contains another recording's data.

These tests build two videos that deliberately share ids -- the same
collision the real corpus has -- and assert each query returns one
video's worth.

DB-backed: they insert, commit (the queries open their own
connections, so uncommitted rows would be invisible to them) and delete
their own rows afterwards.
"""

import pytest

from backend.db import get_db_connection
from backend.queries import stats, videos

# Distinctive enough that a leftover row from a crashed run is
# recognisable, and far outside anything an import would produce.
FILENAMES = ("zz-scoping-test-a.mp4", "zz-scoping-test-b.mp4")
SHARED_EMOTION_ID = 16621
SHARED_PERSON_ID = 1


@pytest.fixture
def two_videos_sharing_ids(db_available):
    """
    Two videos whose person and emotion ids collide, as real CAS
    exports from one pipeline always do.
    """
    if not db_available:
        pytest.skip("no database available")

    conn = get_db_connection()
    video_ids = []
    try:
        with conn.cursor() as cur:
            for index, filename in enumerate(FILENAMES):
                cur.execute(
                    "INSERT INTO videos (filename) VALUES (%s) RETURNING video_id",
                    (filename,),
                )
                video_id = cur.fetchone()[0]
                video_ids.append(video_id)

                cur.execute(
                    "INSERT INTO persons (video_id, person_id, clip_label) "
                    "VALUES (%s, %s, %s)",
                    (video_id, SHARED_PERSON_ID, f"person_{index + 1}"),
                )
                cur.execute(
                    "INSERT INTO base_emotions (video_id, emotion_id, person_id, "
                    "modality, granularity, start_time, end_time, valence) "
                    "VALUES (%s, %s, %s, 'video', 'frame', 1.0, 1.02, %s)",
                    (video_id, SHARED_EMOTION_ID, SHARED_PERSON_ID, 0.5 - index),
                )
                # One label per video, so a leak is visible by name.
                cur.execute(
                    "INSERT INTO emotion_scores (video_id, emotion_id, label, score) "
                    "VALUES (%s, %s, %s, %s)",
                    (video_id, SHARED_EMOTION_ID, f"label_from_video_{index + 1}", 0.9),
                )
        conn.commit()
        yield video_ids
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE video_id = ANY(%s)", (video_ids,))
        conn.commit()
        conn.close()


def test_emotion_scores_come_from_one_video_only(two_videos_sharing_ids):
    first, second = two_videos_sharing_ids

    rows = videos.get_emotion_scores(first, [SHARED_EMOTION_ID])

    assert [r["label"] for r in rows] == ["label_from_video_1"]
    # And the other video sees its own, for the same emotion_id.
    rows = videos.get_emotion_scores(second, [SHARED_EMOTION_ID])
    assert [r["label"] for r in rows] == ["label_from_video_2"]


def test_the_playback_payload_carries_one_video_of_scores(two_videos_sharing_ids):
    first, _second = two_videos_sharing_ids

    payload = videos.build_playback_payload(first)

    scores = payload["emotion_scores"][SHARED_EMOTION_ID]
    assert [s["label"] for s in scores] == ["label_from_video_1"]
    assert len(payload["emotions"]["video"]) == 1


def test_person_averages_do_not_fan_out_across_videos(two_videos_sharing_ids):
    first, _second = two_videos_sharing_ids

    rows = stats.person_emotion_averages(first)

    # One person, one modality, one reading. Joining `persons` on
    # person_id alone would match both videos' person 1 and double it.
    assert len(rows) == 1
    assert rows[0]["n"] == 1
    assert rows[0]["clip_label"] == "person_1"
    assert rows[0]["avg_valence"] == pytest.approx(0.5)


def test_persons_are_listed_per_video(two_videos_sharing_ids):
    first, second = two_videos_sharing_ids

    assert [p["clip_label"] for p in videos.get_persons(first)] == ["person_1"]
    assert [p["clip_label"] for p in videos.get_persons(second)] == ["person_2"]
