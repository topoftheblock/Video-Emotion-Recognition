"""
DB-integration tests for src/main/parsers/global_identity.py.

Everything runs on the `db_cursor` fixture's single connection and is
rolled back at teardown (see conftest.py) -- setup inserts, the
parse() call under test, and the assertion SELECTs all share one
uncommitted transaction, so no cleanup or dedicated test schema is
needed beyond a real Postgres with schema.sql applied.
"""

from main.parsers import global_identity

# Well outside any real CAS's xmi:id range (small integers in
# practice) -- avoids any risk of colliding with genuine committed
# data while these tests' own inserts stay uncommitted anyway.
V1, V2 = 9_100_001, 9_100_002
P1, P2 = 9_100_101, 9_100_102


def _vector_literal(dim, base):
    return "[" + ",".join(f"{base + i * 0.001:.4f}" for i in range(dim)) + "]"


def _seed_video_and_person(cursor, video_id, person_id, clip_label):
    cursor.execute(
        "INSERT INTO videos (video_id, filename) VALUES (%s, %s)",
        (video_id, f"test-{video_id}.mp4"),
    )
    cursor.execute(
        "INSERT INTO persons (person_id, video_id, clip_label) VALUES (%s, %s, %s)",
        (person_id, video_id, clip_label),
    )


def test_links_persons_with_matching_face_embeddings(db_cursor):
    _seed_video_and_person(db_cursor, V1, P1, "person_a")
    _seed_video_and_person(db_cursor, V2, P2, "person_b")

    same_embedding = _vector_literal(512, 1.0)
    db_cursor.execute(
        "INSERT INTO face_embeddings (person_id, embedding) VALUES (%s, %s)",
        (P1, same_embedding),
    )
    db_cursor.execute(
        "INSERT INTO face_embeddings (person_id, embedding) VALUES (%s, %s)",
        (P2, same_embedding),
    )

    # P1's video was "already imported" -- only run the step for V2,
    # same as pipeline.py would on a real second import.
    global_identity.parse(None, db_cursor, {"global_video_id": V2})

    db_cursor.execute(
        "SELECT global_person_id FROM persons WHERE person_id IN (%s, %s)", (P1, P2)
    )
    global_ids = {row[0] for row in db_cursor.fetchall()}
    assert len(global_ids) == 1
    assert None not in global_ids


def test_does_not_link_dissimilar_face_embeddings(db_cursor):
    _seed_video_and_person(db_cursor, V1, P1, "person_a")
    _seed_video_and_person(db_cursor, V2, P2, "person_b")

    db_cursor.execute(
        "INSERT INTO face_embeddings (person_id, embedding) VALUES (%s, %s)",
        (P1, _vector_literal(512, 1.0)),
    )
    db_cursor.execute(
        "INSERT INTO face_embeddings (person_id, embedding) VALUES (%s, %s)",
        (P2, _vector_literal(512, -1.0)),
    )

    global_identity.parse(None, db_cursor, {"global_video_id": V2})

    db_cursor.execute(
        "SELECT global_person_id FROM persons WHERE person_id IN (%s, %s)", (P1, P2)
    )
    assert all(row[0] is None for row in db_cursor.fetchall())


def test_does_not_relink_a_person_that_already_has_a_global_id(db_cursor):
    _seed_video_and_person(db_cursor, V1, P1, "person_a")
    _seed_video_and_person(db_cursor, V2, P2, "person_b")

    db_cursor.execute("INSERT INTO global_persons (real_name) VALUES (NULL) RETURNING global_person_id")
    existing_global_id = db_cursor.fetchone()[0]
    db_cursor.execute("UPDATE persons SET global_person_id = %s WHERE person_id = %s", (existing_global_id, P2))

    same_embedding = _vector_literal(512, 1.0)
    db_cursor.execute("INSERT INTO face_embeddings (person_id, embedding) VALUES (%s, %s)", (P1, same_embedding))
    db_cursor.execute("INSERT INTO face_embeddings (person_id, embedding) VALUES (%s, %s)", (P2, same_embedding))

    # Run the step for V2 -- P2 already has a global_person_id, so it
    # must be left alone rather than re-matched/overwritten.
    global_identity.parse(None, db_cursor, {"global_video_id": V2})

    db_cursor.execute("SELECT global_person_id FROM persons WHERE person_id = %s", (P2,))
    assert db_cursor.fetchone()[0] == existing_global_id
