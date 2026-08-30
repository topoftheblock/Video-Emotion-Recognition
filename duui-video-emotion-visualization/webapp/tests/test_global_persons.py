"""Tests the read side of the people linked across videos.

`list_global_clusters` is the only query behind `/api/persons/global`,
and the panel that shows "also appears in" is the one feature that
depends on the identity linker having run. Nothing exercised it before.

The shape it returns is not a row list: it groups the flat join into one
entry per global person, with its members. That grouping is the logic
worth testing, and it is invisible from the SQL alone.

Database-backed. It builds two videos, one person in each linked to the
same global person, and removes them again.
"""

from collections.abc import Iterator

import pytest

from backend.db import get_db_connection
from backend.queries import persons

FILENAMES = ("zz-global-a.mp4", "zz-global-b.mp4")


@pytest.fixture
def one_person_across_two_videos(db_available: bool) -> Iterator[int]:
    """Link one person in each of two videos to a single global person.

    Committed rather than held in a transaction, because the query under
    test opens its own connection.
    """
    if not db_available:
        pytest.skip("no database available")

    conn = get_db_connection()
    video_ids: list[int] = []
    global_person_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO global_persons (real_name) VALUES (%s) "
                "RETURNING global_person_id",
                ("Test Person",),
            )
            global_person_id = cur.fetchone()[0]

            for index, filename in enumerate(FILENAMES):
                cur.execute(
                    "INSERT INTO videos (filename) VALUES (%s) RETURNING video_id",
                    (filename,),
                )
                video_id = cur.fetchone()[0]
                video_ids.append(video_id)
                cur.execute(
                    "INSERT INTO persons "
                    "(video_id, person_id, clip_label, global_person_id, "
                    "global_person_match_score) VALUES (%s, 1, %s, %s, %s)",
                    (video_id, f"person_{index}", global_person_id, 0.1 * index),
                )
        conn.commit()
        yield global_person_id
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM videos WHERE video_id = ANY(%s)", (video_ids,))
            if global_person_id is not None:
                cur.execute(
                    "DELETE FROM global_persons WHERE global_person_id = %s",
                    (global_person_id,),
                )
        conn.commit()
        conn.close()


def _cluster(clusters: list[dict], global_person_id: int) -> dict:
    """The one entry for this global person."""
    matching = [c for c in clusters if c["global_person_id"] == global_person_id]
    assert len(matching) == 1, f"expected one entry, got {len(matching)}"
    return matching[0]


def test_a_global_person_is_one_entry_with_its_members(
    one_person_across_two_videos: int,
) -> None:
    """The flat join is grouped, not returned a row at a time."""
    cluster = _cluster(persons.list_global_clusters(), one_person_across_two_videos)

    assert cluster["real_name"] == "Test Person"
    assert len(cluster["members"]) == 2


def test_each_member_names_the_video_it_came_from(
    one_person_across_two_videos: int,
) -> None:
    """Without it the panel cannot say where else someone appears."""
    cluster = _cluster(persons.list_global_clusters(), one_person_across_two_videos)

    assert sorted(m["video_filename"] for m in cluster["members"]) == sorted(FILENAMES)


def test_each_member_carries_its_own_match_score(
    one_person_across_two_videos: int,
) -> None:
    """The score is per member, since each was matched separately."""
    cluster = _cluster(persons.list_global_clusters(), one_person_across_two_videos)

    scores = sorted(m["global_person_match_score"] for m in cluster["members"])
    assert scores == [pytest.approx(0.0), pytest.approx(0.1)]


def test_an_unlinked_person_does_not_appear(
    one_person_across_two_videos: int,
) -> None:
    """The query answers "who spans videos", not "everyone".

    A third person is added to one of the videos with no link at all.
    They must not show up as a member of anything.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT video_id FROM videos WHERE filename = %s", (FILENAMES[0],)
            )
            video_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO persons (video_id, person_id, clip_label) "
                "VALUES (%s, 99, 'unlinked_person')",
                (video_id,),
            )
        conn.commit()
    finally:
        conn.close()

    members = [
        member
        for cluster in persons.list_global_clusters()
        for member in cluster["members"]
    ]

    assert not [m for m in members if m["clip_label"] == "unlinked_person"], (
        "a person with no global_person_id is not part of any global person"
    )
    # The two that are linked are still there, so the query did not
    # simply return nothing.
    assert (
        len(
            _cluster(persons.list_global_clusters(), one_person_across_two_videos)[
                "members"
            ]
        )
        == 2
    )
