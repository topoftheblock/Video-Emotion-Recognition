"""
DB-integration tests for src/identity/linking.py.

Everything runs on the `db_cursor` fixture's single connection and is
rolled back at teardown (see conftest.py) -- setup inserts, the calls
under test, and the assertion SELECTs all share one uncommitted
transaction, so no cleanup or dedicated test schema is needed beyond a
real Postgres with schema.sql applied.

Note that `clear_global_identities` (and therefore
`recompute_global_identities`) wipes `global_persons` corpus-wide, not
just the rows a test inserted. That is the behaviour under test, and
the fixture's rollback is what keeps it from touching a populated
database for real.
"""

import pytest

from identity import linking

# Well outside any real CAS's xmi:id range (small integers in
# practice) -- avoids any risk of colliding with genuine committed
# data while these tests' own inserts stay uncommitted anyway.
V1, V2 = 9_100_001, 9_100_002
P1, P2 = 9_100_101, 9_100_102
P3 = 9_100_103


# The two embedding columns are different widths (see db/schema.sql):
# 512-dim face vectors, 192-dim voiceprints. Inserting the wrong width
# is a hard error from pgvector, so the tests derive it from the table.
_DIMENSIONS = {"face_embeddings": 512, "voice_embeddings": 192}


def _vector_literal(dim, base):
    return "[" + ",".join(f"{base + i * 0.001:.4f}" for i in range(dim)) + "]"


def _seed_video_and_person(cursor, video_id, person_id, clip_label):
    cursor.execute(
        "INSERT INTO videos (video_id, filename) VALUES (%s, %s) "
        "ON CONFLICT (video_id) DO NOTHING",
        (video_id, f"test-{video_id}.mp4"),
    )
    cursor.execute(
        "INSERT INTO persons (person_id, video_id, clip_label) VALUES (%s, %s, %s)",
        (person_id, video_id, clip_label),
    )


def _embed(cursor, table, person_id, base):
    cursor.execute(
        f"INSERT INTO {table} (person_id, embedding) VALUES (%s, %s)",
        (person_id, _vector_literal(_DIMENSIONS[table], base)),
    )


def _global_ids(cursor, *person_ids):
    cursor.execute(
        "SELECT person_id, global_person_id FROM persons WHERE person_id = ANY(%s)",
        (list(person_ids),),
    )
    return dict(cursor.fetchall())


@pytest.fixture
def linkable(db_cursor):
    """Two people in two different videos, nothing linked yet."""
    _seed_video_and_person(db_cursor, V1, P1, "person_a")
    _seed_video_and_person(db_cursor, V2, P2, "person_b")
    return db_cursor


def test_links_persons_with_matching_face_embeddings(linkable):
    _embed(linkable, "face_embeddings", P1, 1.0)
    _embed(linkable, "face_embeddings", P2, 1.0)

    linking.build_centroids(linkable)
    linking.link_person(linkable, P2)

    ids = _global_ids(linkable, P1, P2)
    assert ids[P1] is not None
    # Both sides of a match land on one shared identity -- the point of
    # the whole job.
    assert ids[P1] == ids[P2]


def test_does_not_link_dissimilar_face_embeddings(linkable):
    _embed(linkable, "face_embeddings", P1, 1.0)
    _embed(linkable, "face_embeddings", P2, -1.0)

    linking.build_centroids(linkable)
    linking.link_person(linkable, P2)

    assert _global_ids(linkable, P1, P2) == {P1: None, P2: None}


def test_falls_back_to_voice_when_there_are_no_face_embeddings(linkable):
    _embed(linkable, "voice_embeddings", P1, 1.0)
    _embed(linkable, "voice_embeddings", P2, 1.0)

    linking.build_centroids(linkable)
    linking.link_person(linkable, P2)

    ids = _global_ids(linkable, P1, P2)
    assert ids[P1] is not None
    assert ids[P1] == ids[P2]


def test_does_not_link_two_people_from_the_same_video(db_cursor):
    # Identical embeddings, same video: two tracks of one person within
    # one recording are the importer's business, not a *cross*-video
    # identity, and merging them here would invent a global identity
    # that spans exactly one video.
    _seed_video_and_person(db_cursor, V1, P1, "person_a")
    db_cursor.execute(
        "INSERT INTO persons (person_id, video_id, clip_label) VALUES (%s, %s, %s)",
        (P3, V1, "person_a_again"),
    )
    _embed(db_cursor, "face_embeddings", P1, 1.0)
    _embed(db_cursor, "face_embeddings", P3, 1.0)

    linking.build_centroids(db_cursor)
    linking.link_person(db_cursor, P3)

    assert _global_ids(db_cursor, P1, P3) == {P1: None, P3: None}


def test_does_not_relink_a_person_that_already_has_a_global_id(linkable):
    linkable.execute(
        "INSERT INTO global_persons (real_name) VALUES (NULL) RETURNING global_person_id"
    )
    existing_global_id = linkable.fetchone()[0]
    linkable.execute(
        "UPDATE persons SET global_person_id = %s WHERE person_id = %s",
        (existing_global_id, P2),
    )

    _embed(linkable, "face_embeddings", P1, 1.0)
    _embed(linkable, "face_embeddings", P2, 1.0)

    linking.build_centroids(linkable)
    # P2 was already assigned -- during a real run that means an earlier
    # person in the loop matched it and pulled it into a group, so
    # linking it again would split the group that was just formed.
    linking.link_person(linkable, P2)

    assert _global_ids(linkable, P2)[P2] == existing_global_id


def test_clear_removes_every_global_identity(linkable):
    linkable.execute(
        "INSERT INTO global_persons (real_name) VALUES (NULL) RETURNING global_person_id"
    )
    global_id = linkable.fetchone()[0]
    linkable.execute(
        "UPDATE persons SET global_person_id = %s WHERE person_id = ANY(%s)",
        (global_id, [P1, P2]),
    )

    persons_unlinked, identities_deleted = linking.clear_global_identities(linkable)

    assert persons_unlinked >= 2
    assert identities_deleted >= 1
    assert _global_ids(linkable, P1, P2) == {P1: None, P2: None}
    linkable.execute("SELECT count(*) FROM global_persons")
    assert linkable.fetchone()[0] == 0


def test_recompute_clears_stale_identities_and_rebuilds_from_embeddings(linkable):
    # A stale identity that the embeddings do NOT justify: P1 and P2
    # look nothing alike, so a full recompute has to drop this rather
    # than preserve it. This is the case the old per-import step could
    # never fix -- it only ever added links.
    linkable.execute(
        "INSERT INTO global_persons (real_name) VALUES (NULL) RETURNING global_person_id"
    )
    stale_global_id = linkable.fetchone()[0]
    linkable.execute(
        "UPDATE persons SET global_person_id = %s WHERE person_id = ANY(%s)",
        (stale_global_id, [P1, P2]),
    )

    _embed(linkable, "face_embeddings", P1, 1.0)
    _embed(linkable, "face_embeddings", P2, -1.0)

    stats = linking.recompute_global_identities(linkable)

    assert _global_ids(linkable, P1, P2) == {P1: None, P2: None}
    linkable.execute(
        "SELECT count(*) FROM global_persons WHERE global_person_id = %s",
        (stale_global_id,),
    )
    assert linkable.fetchone()[0] == 0
    assert stats["identities_deleted"] >= 1
    assert stats["persons_total"] >= 2


def test_recompute_links_matching_persons_regardless_of_insert_order(linkable):
    # The whole point of recomputing corpus-wide: P1's video was
    # "imported" first, so the old per-video step running for V1 could
    # not have seen P2 at all. A full pass links them either way.
    _embed(linkable, "face_embeddings", P1, 1.0)
    _embed(linkable, "face_embeddings", P2, 1.0)

    linking.recompute_global_identities(linkable)

    ids = _global_ids(linkable, P1, P2)
    assert ids[P1] is not None
    assert ids[P1] == ids[P2]
