"""Tests that the webapp's queries never read across videos.

Every id that came out of a CAS — an emotion, a person, a segment — is
unique only within one video, so a query filtering or joining on one of
them alone silently pulls in other videos' rows. The failure is not an
error: it is a payload that looks right and holds another video's data.

These build two videos that deliberately share ids, which is what
separate exports from one pipeline produce, and assert that each query
returns one video's worth.

Database-backed. They insert, commit — the queries open their own
connections, so uncommitted rows would be invisible to them — and
delete their own rows afterwards.
"""

from collections.abc import Iterator

import pytest

from backend.db import get_db_connection
from backend.queries import stats, videos

# Distinctive enough that a row left behind by a crashed run is
# recognisable, and outside anything an import would produce.
FILENAMES = ("zz-scoping-test-a.mp4", "zz-scoping-test-b.mp4")
SHARED_EMOTION_ID = 16621
SHARED_PERSON_ID = 1


@pytest.fixture
def two_videos_sharing_ids(db_available: bool) -> Iterator[tuple[int, int]]:
    """Build two videos whose person and emotion ids collide."""
    if not db_available:
        pytest.skip("no database available")

    conn = get_db_connection()
    video_ids: list[int] = []
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
        first, second = video_ids
        yield (first, second)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE video_id = ANY(%s)", (video_ids,))
        conn.commit()
        conn.close()


def test_emotion_scores_come_from_one_video_only(
    two_videos_sharing_ids: tuple[int, int],
) -> None:
    """One id, two videos, two different sets of scores."""
    first, second = two_videos_sharing_ids

    rows = videos.get_emotion_scores(first, [SHARED_EMOTION_ID])

    assert [r["label"] for r in rows] == ["label_from_video_1"]
    # And the other video sees its own, for the same emotion_id.
    rows = videos.get_emotion_scores(second, [SHARED_EMOTION_ID])
    assert [r["label"] for r in rows] == ["label_from_video_2"]


def test_the_playback_payload_carries_one_video_of_scores(
    two_videos_sharing_ids: tuple[int, int],
) -> None:
    """The assembled payload never picks up the other video's rows."""
    first, _second = two_videos_sharing_ids

    payload = videos.build_playback_payload(first)
    assert payload is not None

    scores = payload["emotion_scores"][SHARED_EMOTION_ID]
    assert [s["label"] for s in scores] == ["label_from_video_1"]
    assert len(payload["emotions"]["video"]) == 1


def test_person_averages_do_not_fan_out_across_videos(
    two_videos_sharing_ids: tuple[int, int],
) -> None:
    """Joining on the person alone would double every reading."""
    first, _second = two_videos_sharing_ids

    rows = stats.person_emotion_averages(first)

    # One person, one modality, one reading. Joining `persons` on
    # person_id alone would match both videos' person 1 and double it.
    assert len(rows) == 1
    assert rows[0]["n"] == 1
    assert rows[0]["clip_label"] == "person_1"
    assert rows[0]["avg_valence"] == pytest.approx(0.5)


def test_persons_are_listed_per_video(
    two_videos_sharing_ids: tuple[int, int],
) -> None:
    """Each video lists its own people, not the other's."""
    first, second = two_videos_sharing_ids

    assert [p["clip_label"] for p in videos.get_persons(first)] == ["person_1"]
    assert [p["clip_label"] for p in videos.get_persons(second)] == ["person_2"]
