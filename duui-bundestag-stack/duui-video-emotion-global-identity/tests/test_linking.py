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
#
# A person is a (video_id, person_id) pair everywhere in this module,
# because person ids are only unique within one video: every CAS
# numbers its own annotations from 1, so "person 1" exists in every
# video in the corpus (see db/schema.sql's identity note). P1 and P3
# deliberately share V1 to keep that visible.
V1, V2, V3 = 9_100_001, 9_100_002, 9_100_003
P1, P2, P3 = (V1, 9_100_101), (V2, 9_100_102), (V1, 9_100_103)
P4 = (V3, 9_100_104)


# The two embedding columns are different widths (see db/schema.sql):
# 512-dim face vectors, 192-dim voiceprints. Inserting the wrong width
# is a hard error from pgvector, so the tests derive it from the table.
_DIMENSIONS = {"face_embeddings": 512, "voice_embeddings": 192}


def _vector_literal(dim, base):
    return "[" + ",".join(f"{base + i * 0.001:.4f}" for i in range(dim)) + "]"


def _opposite_vector(dim, base):
    # Exact negation of _vector_literal -- cosine distance to it is 2.0.
    return "[" + ",".join(f"{-(base + i * 0.001):.4f}" for i in range(dim)) + "]"


def _seed_person(cursor, person, clip_label):
    video_id, person_id = person
    cursor.execute(
        "INSERT INTO videos (video_id, filename) VALUES (%s, %s) "
        "ON CONFLICT (video_id) DO NOTHING",
        (video_id, f"test-{video_id}.mp4"),
    )
    cursor.execute(
        "INSERT INTO persons (video_id, person_id, clip_label) VALUES (%s, %s, %s)",
        (video_id, person_id, clip_label),
    )


def _embed(cursor, table, person, base, embedding_id=None, invert=False):
    video_id, person_id = person
    vec = _opposite_vector(_DIMENSIONS[table], base) if invert else _vector_literal(_DIMENSIONS[table], base)
    cursor.execute(
        f"INSERT INTO {table} (video_id, embedding_id, person_id, embedding) "
        f"VALUES (%s, %s, %s, %s)",
        (
            video_id,
            embedding_id if embedding_id is not None else person_id,
            person_id,
            vec,
        ),
    )


def _global_ids(cursor, *persons):
    """global_person_id per (video_id, person_id), for the given people."""
    result = {}
    for video_id, person_id in persons:
        cursor.execute(
            "SELECT global_person_id FROM persons WHERE video_id = %s AND person_id = %s",
            (video_id, person_id),
        )
        row = cursor.fetchone()
        result[(video_id, person_id)] = row[0] if row else None
    return result


def _match_scores(cursor, *persons):
    """global_person_match_score per (video_id, person_id), for the given people."""
    result = {}
    for video_id, person_id in persons:
        cursor.execute(
            "SELECT global_person_match_score FROM persons WHERE video_id = %s AND person_id = %s",
            (video_id, person_id),
        )
        row = cursor.fetchone()
        result[(video_id, person_id)] = row[0] if row else None
    return result


@pytest.fixture
def linkable(db_cursor):
    """Two people in two different videos, nothing linked yet."""
    _seed_person(db_cursor, P1, "person_a")
    _seed_person(db_cursor, P2, "person_b")
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
    _seed_person(db_cursor, P1, "person_a")
    _seed_person(db_cursor, P3, "person_a_again")
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
        "UPDATE persons SET global_person_id = %s WHERE video_id = %s AND person_id = %s",
        (existing_global_id, *P2),
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
        "UPDATE persons SET global_person_id = %s "
        "WHERE (video_id, person_id) IN (%s, %s)",
        (global_id, P1, P2),
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
        "UPDATE persons SET global_person_id = %s "
        "WHERE (video_id, person_id) IN (%s, %s)",
        (stale_global_id, P1, P2),
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


def test_recompute_writes_global_person_match_score(db_cursor):
    # P1 (V1) and P4 (V3) have identical face centroids (cross-video
    # distance ~0); P2 (V2) is the opposite (distance ~2).
    # global_person_match_score is each person's nearest *cross-video*
    # centroid distance, written for everyone -- linked or not -- so P1
    # and P4 get ~0 while P2, whose only cross-video neighbour is 2.0
    # away, gets ~2 (and stays unlinked past the 0.30 threshold).
    _seed_person(db_cursor, P1, "person_a")
    _seed_person(db_cursor, P2, "person_b")
    _seed_person(db_cursor, P4, "person_a_again")
    _embed(db_cursor, "face_embeddings", P1, 1.0)
    _embed(db_cursor, "face_embeddings", P2, 1.0, invert=True)
    _embed(db_cursor, "face_embeddings", P4, 1.0)

    linking.recompute_global_identities(db_cursor)

    ids = _global_ids(db_cursor, P1, P2, P4)
    assert ids[P1] is not None and ids[P1] == ids[P4]
    assert ids[P2] is None

    scores = _match_scores(db_cursor, P1, P2, P4)
    assert scores[P1] == pytest.approx(0.0, abs=1e-6)
    assert scores[P4] == pytest.approx(0.0, abs=1e-6)
    assert scores[P2] == pytest.approx(2.0, abs=1e-6)


def test_global_person_match_score_is_order_independent(db_cursor):
    # The score is a pure function of the centroids, so a full recompute
    # (which runs _write_match_scores after the link loop) must yield
    # identical scores on a second pass after a clear -- the value does
    # not depend on which person was linked first.
    _seed_person(db_cursor, P1, "person_a")
    _seed_person(db_cursor, P2, "person_b")
    _seed_person(db_cursor, P4, "person_a_again")
    _embed(db_cursor, "face_embeddings", P1, 1.0)
    _embed(db_cursor, "face_embeddings", P2, 1.0, invert=True)
    _embed(db_cursor, "face_embeddings", P4, 1.0)

    linking.recompute_global_identities(db_cursor)
    first = _match_scores(db_cursor, P1, P2, P4)

    linking.clear_global_identities(db_cursor)
    linking.recompute_global_identities(db_cursor)
    second = _match_scores(db_cursor, P1, P2, P4)

    assert first == second
    assert second[P1] == pytest.approx(0.0, abs=1e-6)
    assert second[P2] == pytest.approx(2.0, abs=1e-6)


def test_clear_also_nulls_global_person_match_score(db_cursor):
    # clear_global_identities resets the score alongside global_person_id
    # (it is meaningless once the links it describes are gone), but must
    # not touch audio_video_match_score -- that is the importer's value.
    _seed_person(db_cursor, P1, "person_a")
    _seed_person(db_cursor, P2, "person_b")
    _embed(db_cursor, "face_embeddings", P1, 1.0)
    _embed(db_cursor, "face_embeddings", P2, 1.0, invert=True)
    db_cursor.execute(
        "UPDATE persons SET audio_video_match_score = 0.83 WHERE (video_id, person_id) = %s",
        (P1,),
    )

    linking.recompute_global_identities(db_cursor)
    db_cursor.execute(
        "SELECT global_person_match_score, audio_video_match_score FROM persons "
        "WHERE (video_id, person_id) = %s",
        (P1,),
    )
    before_score, before_av = db_cursor.fetchone()
    assert before_score is not None

    linking.clear_global_identities(db_cursor)
    db_cursor.execute(
        "SELECT global_person_match_score, audio_video_match_score FROM persons "
        "WHERE (video_id, person_id) = %s",
        (P1,),
    )
    after_score, after_av = db_cursor.fetchone()
    assert after_score is None
    assert after_av == 0.83
