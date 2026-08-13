"""
Vector-based cross-video person identity.

The schema has always had `global_persons`/`persons.global_person_id`
for "the same person across multiple videos", but nothing ever
populated it: the real Bundestag CAS never encodes a `GlobalPerson`
link itself (confirmed empty in every real CAS this parser has been
run against), so without this step every video's persons stay
permanently isolated from each other.

This step runs once per imported video, after `person` (so this
video's `persons` rows exist) and `embedding` (so this video's
face/voice embeddings exist). For every person in the current video
that doesn't already have a global_person_id, it looks for the
closest-matching person from any *other* already-imported video by
pgvector cosine distance between embedding centroids, and either joins
an existing global identity or mints a new one shared by both sides.

This is a similarity heuristic, not a verified identity match --
`match_score`/the distance itself is not stored per-link (the schema
has no column for it), so treat `global_person_id` groupings as
"probably the same person", not ground truth, and retune the distance
thresholds in config.py against real cross-video duplicates before
relying on this for anything beyond suggestions or the query agent's
own use.
"""

from ..config import (
    ENABLE_GLOBAL_PERSON_LINKING,
    GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD,
    GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD,
)

# Average multiple embeddings per person into one centroid before
# comparing (pgvector supports `avg()` over the vector type directly)
# rather than doing a full N*M nearest-neighbor search across every
# individual embedding row -- a person can have dozens of face
# embeddings (one per detection frame), and the identity signal is the
# same person's face across those frames, not any single frame.
_CENTROID_MATCH_SQL = """
WITH centroids AS (
    SELECT person_id, avg(embedding) AS centroid
    FROM {table}
    GROUP BY person_id
)
SELECT c2.person_id, p2.global_person_id, (c1.centroid <=> c2.centroid) AS distance
FROM centroids c1
JOIN persons p1 ON p1.person_id = c1.person_id
JOIN centroids c2 ON c2.person_id != c1.person_id
JOIN persons p2 ON p2.person_id = c2.person_id AND p2.video_id != p1.video_id
WHERE c1.person_id = %s
ORDER BY distance ASC
LIMIT 1
"""


def _best_cross_video_match(cursor, person_id, table, threshold):
    """
    Returns (candidate_person_id, candidate_global_person_id, distance)
    for the closest other-video person by embedding centroid, or None
    if there is no candidate at all or the closest one is farther than
    `threshold` (pgvector cosine distance -- lower is more similar).
    """
    cursor.execute(_CENTROID_MATCH_SQL.format(table=table), (person_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    candidate_person_id, candidate_global_person_id, distance = row
    if distance is None or distance > threshold:
        return None
    return candidate_person_id, candidate_global_person_id, distance


def _create_global_person(cursor):
    cursor.execute("INSERT INTO global_persons (real_name) VALUES (NULL) RETURNING global_person_id")
    return cursor.fetchone()[0]


def _assign_global_person(cursor, person_id, global_person_id):
    cursor.execute(
        "UPDATE persons SET global_person_id = %s WHERE person_id = %s",
        (global_person_id, person_id),
    )


def parse(cas, cursor, context):
    if not ENABLE_GLOBAL_PERSON_LINKING:
        return

    video_id = context.get("global_video_id")
    if video_id is None:
        return

    cursor.execute(
        "SELECT person_id, global_person_id FROM persons WHERE video_id = %s",
        (video_id,),
    )
    persons = cursor.fetchall()

    for person_id, existing_global_id in persons:
        if existing_global_id is not None:
            # Already resolved -- e.g. the CAS itself provided a
            # GlobalPerson link. Don't second-guess it with a
            # heuristic vector match.
            continue

        match = _best_cross_video_match(
            cursor, person_id, "face_embeddings", GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD
        )
        if match is None:
            # Fall back to voice: a person with no usable face
            # embedding (never clearly on camera, or face embedding
            # extraction failed) can still be linked by voiceprint.
            match = _best_cross_video_match(
                cursor, person_id, "voice_embeddings", GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD
            )
        if match is None:
            continue

        candidate_person_id, candidate_global_id, _distance = match
        global_id = candidate_global_id if candidate_global_id is not None else _create_global_person(cursor)

        _assign_global_person(cursor, person_id, global_id)
        if candidate_global_id is None:
            _assign_global_person(cursor, candidate_person_id, global_id)
