"""
Vector-based cross-video person identity.

The schema has always had `global_persons`/`persons.global_person_id`
for "the same person across multiple videos", but nothing in the
importer populates it: the real Bundestag CAS never encodes a
`GlobalPerson` link itself (confirmed empty in every real CAS this was
run against, and the type isn't even present in the shipped
typesystems), so without this job every video's persons stay
permanently isolated from each other.

This used to run as a parse step inside the importer, once per imported
video, which made the result depend on import order: a person could
only ever match against videos that happened to be imported before it.
As a standalone job it instead does a full recompute over the whole
corpus -- it wipes every existing global identity first, then rebuilds
them from scratch -- so the outcome depends only on what is in the
database, not on the order it arrived in. That is also why it must be
run explicitly: it is corpus-wide, and re-running it after each import
is a deliberate choice rather than a per-file side effect.

For every person that doesn't yet have a global_person_id, it looks for
the closest-matching person from any *other* video by pgvector cosine
distance between embedding centroids, and either joins an existing
global identity or mints a new one shared by both sides.

This is a similarity heuristic, not a verified identity match --
`match_score`/the distance itself is not stored per-link (the schema
has no column for it), so treat `global_person_id` groupings as
"probably the same person", not ground truth, and retune the distance
thresholds in config.py against real cross-video duplicates before
relying on this for anything beyond suggestions or the query agent's
own use.
"""

from .config import (
    GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD,
    GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD,
)

# Average multiple embeddings per person into one centroid before
# comparing (pgvector supports `avg()` over the vector type directly)
# rather than doing a full N*M nearest-neighbor search across every
# individual embedding row -- a person can have dozens of face
# embeddings (one per detection frame), and the identity signal is the
# same person's face across those frames, not any single frame.
#
# Materialised into a TEMP TABLE once per run rather than recomputed as
# a CTE inside every per-person lookup. While this ran per-import it
# only ever executed for one video's handful of people; a full-corpus
# recompute does one lookup per person in the database, and rebuilding
# every centroid inside each of those means re-scanning the whole
# embeddings table N times over.
#
# A person is identified by (video_id, person_id), never by person_id
# alone: person ids come from each CAS's own xmi:id counter, so two
# videos routinely both have a "person 1" (see db/schema.sql's identity
# note). Every join and lookup in this module therefore carries the
# pair, and the embeddings table carries `video_id` itself -- which is
# also why this no longer joins back to `persons` just to find out
# which video an embedding belongs to.
_BUILD_CENTROIDS_SQL = """
CREATE TEMP TABLE {temp_table} AS
SELECT e.video_id, e.person_id, avg(e.embedding) AS centroid
FROM {source_table} e
WHERE e.person_id IS NOT NULL
GROUP BY e.video_id, e.person_id
"""

# `global_person_id` is read live from `persons` rather than from the
# temp table: the loop below assigns ids as it goes, and a candidate
# matched earlier in this same run must be seen with the id it was just
# given, not the NULL it started with.
#
# Comparing video_id alone is enough to exclude the person themselves
# (a person belongs to exactly one video). A NULL video_id on either
# side makes the comparison NULL and drops the row -- a person not
# attached to any video can't be said to appear in a *different* one.
_MATCH_SQL = """
SELECT c2.video_id, c2.person_id, p2.global_person_id,
       (c1.centroid <=> c2.centroid) AS distance
FROM {temp_table} c1
JOIN {temp_table} c2 ON c2.video_id != c1.video_id
JOIN persons p2 ON p2.video_id = c2.video_id AND p2.person_id = c2.person_id
WHERE c1.video_id = %s AND c1.person_id = %s
ORDER BY distance ASC
LIMIT 1
"""

# (temp table name, embeddings table it is built from, distance threshold).
# Ordered: face is tried first, voice is the fallback -- a person with
# no usable face embedding (never clearly on camera, or face embedding
# extraction failed) can still be linked by voiceprint.
#
# Explicitly schema-qualified with `pg_temp` everywhere: unqualified,
# both the DROP and the lookups would silently act on a permanent table
# of the same name if the schema ever grew one, and dropping a real
# table here would be a very bad way to find that out.
_MODALITIES = (
    ("pg_temp.face_centroids", "face_embeddings", GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD),
    ("pg_temp.voice_centroids", "voice_embeddings", GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD),
)


def clear_global_identities(cursor):
    """
    Drop every existing global identity, so the recompute below starts
    from a clean slate. Returns (persons_unlinked, identities_deleted).

    `global_person_match_score` (computed by this job) is wiped alongside
    `global_person_id`; `audio_video_match_score` is the importer's value
    and is left untouched.

    Both statements are issued explicitly rather than leaning on
    `persons.global_person_id`'s ON DELETE SET NULL: the FK would cover
    the un-linking, but relying on it makes the wipe look like it only
    touches one table when it in fact rewrites both, and the row counts
    reported here are what tells the operator how much the previous run
    had actually linked.
    """
    cursor.execute("SELECT count(*) FROM persons WHERE global_person_id IS NOT NULL")
    persons_unlinked = cursor.fetchone()[0]

    cursor.execute(
        "UPDATE persons SET global_person_id = NULL, global_person_match_score = NULL"
    )

    cursor.execute("DELETE FROM global_persons")
    identities_deleted = cursor.rowcount

    return persons_unlinked, identities_deleted


def build_centroids(cursor):
    """
    Build the per-person face/voice embedding centroid temp tables this
    run's lookups read from.

    Temp tables live for the session, so they go away when the job's
    connection closes; the DROP makes calling this twice on one
    connection work rather than failing on the second build.
    """
    for temp_table, source_table, _threshold in _MODALITIES:
        cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")
        cursor.execute(
            _BUILD_CENTROIDS_SQL.format(temp_table=temp_table, source_table=source_table)
        )
        # Without stats on a freshly created temp table the planner
        # assumes a token row count and can pick a nested loop that is
        # badly wrong once the corpus is real.
        cursor.execute(f"ANALYZE {temp_table}")


def _best_cross_video_match(cursor, person, temp_table, threshold):
    """
    Returns (candidate_person, candidate_global_person_id, distance)
    for the closest other-video person by embedding centroid, or None
    if there is no candidate at all or the closest one is farther than
    `threshold` (pgvector cosine distance -- lower is more similar).

    `person` and `candidate_person` are (video_id, person_id) pairs.
    """
    cursor.execute(_MATCH_SQL.format(temp_table=temp_table), person)
    row = cursor.fetchone()
    if row is None:
        return None
    candidate_video_id, candidate_person_id, candidate_global_person_id, distance = row
    if distance is None or distance > threshold:
        return None
    return (
        (candidate_video_id, candidate_person_id),
        candidate_global_person_id,
        distance,
    )


def _create_global_person(cursor):
    cursor.execute("INSERT INTO global_persons (real_name) VALUES (NULL) RETURNING global_person_id")
    return cursor.fetchone()[0]


def _assign_global_person(cursor, person, global_person_id):
    video_id, person_id = person
    cursor.execute(
        "UPDATE persons SET global_person_id = %s WHERE video_id = %s AND person_id = %s",
        (global_person_id, video_id, person_id),
    )


def _current_global_person_id(cursor, person):
    video_id, person_id = person
    cursor.execute(
        "SELECT global_person_id FROM persons WHERE video_id = %s AND person_id = %s",
        (video_id, person_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def link_person(cursor, person):
    """
    Link one person -- a (video_id, person_id) pair -- to a global
    identity if a close enough person from another video exists.
    Returns the global_person_id it ended up with, or None if it stays
    unlinked.

    Assumes `build_centroids` has already run on this cursor.
    """
    # Re-read rather than trusting a snapshot taken before the loop: an
    # earlier person in this run may have matched *this* one and
    # already assigned it an id, and linking it a second time would
    # split a group that was just joined.
    if _current_global_person_id(cursor, person) is not None:
        return None

    match = None
    for temp_table, _source_table, threshold in _MODALITIES:
        match = _best_cross_video_match(cursor, person, temp_table, threshold)
        if match is not None:
            break
    if match is None:
        return None

    candidate_person, candidate_global_id, _distance = match
    global_id = candidate_global_id if candidate_global_id is not None else _create_global_person(cursor)

    _assign_global_person(cursor, person, global_id)
    if candidate_global_id is None:
        _assign_global_person(cursor, candidate_person, global_id)

    return global_id


def _write_match_scores(cursor):
    """
    Persist each person's nearest cross-video embedding-centroid distance
    as `persons.global_person_match_score`.

    For every person with at least one face or voice centroid, this is the
    minimum cosine distance (`<=>`) to any person in a *different* video;
    face and voice are both tried and the smaller wins (NULL-safe). It is a
    pure function of the centroids -- independent of the order persons were
    linked in -- so it is identical on every recompute. Persons with no
    embeddings in any modality are left NULL.
    """
    cursor.execute(
        """
        UPDATE persons p
        SET global_person_match_score = sub.best
        FROM (
            SELECT
                k.video_id, k.person_id,
                CASE
                    WHEN f.min_d IS NULL THEN v.min_d
                    WHEN v.min_d IS NULL THEN f.min_d
                    ELSE LEAST(f.min_d, v.min_d)
                END AS best
            FROM (
                SELECT video_id, person_id FROM pg_temp.face_centroids
                UNION
                SELECT video_id, person_id FROM pg_temp.voice_centroids
            ) k
            LEFT JOIN pg_temp.face_centroids kf
                ON kf.video_id = k.video_id AND kf.person_id = k.person_id
            LEFT JOIN pg_temp.voice_centroids kv
                ON kv.video_id = k.video_id AND kv.person_id = k.person_id
            LEFT JOIN LATERAL (
                SELECT MIN(kf.centroid <=> oc.centroid) AS min_d
                FROM pg_temp.face_centroids oc
                WHERE oc.video_id <> kf.video_id
            ) f ON true
            LEFT JOIN LATERAL (
                SELECT MIN(kv.centroid <=> oc2.centroid) AS min_d
                FROM pg_temp.voice_centroids oc2
                WHERE oc2.video_id <> kv.video_id
            ) v ON true
        ) sub
        WHERE p.video_id = sub.video_id AND p.person_id = sub.person_id
        """
    )


def recompute_global_identities(cursor, progress=None):
    """
    Wipe every global identity and rebuild them across the whole
    corpus. Returns a dict of counts for the caller to report.

    Persons are walked in (video_id, person_id) order purely so a run
    is reproducible; because everything starts unlinked, the order
    affects only which side of a pair mints the shared row, not who
    ends up grouped with whom.

    Takes a cursor rather than opening its own connection: the entire
    run -- wipe included -- has to be one transaction, so that a
    failure halfway through leaves the previous identities intact
    instead of a corpus that has been cleared but not rebuilt.
    """
    persons_unlinked, identities_deleted = clear_global_identities(cursor)

    build_centroids(cursor)

    cursor.execute("SELECT video_id, person_id FROM persons ORDER BY video_id, person_id")
    persons = cursor.fetchall()

    linked_ids = set()
    for index, person in enumerate(persons, start=1):
        global_id = link_person(cursor, person)
        if global_id is not None:
            linked_ids.add(global_id)
        if progress is not None:
            progress(index, len(persons))

    # Each person's nearest cross-video centroid distance, persisted as
    # global_person_match_score (order-independent -- see _write_match_scores).
    _write_match_scores(cursor)

    # Counted from `persons` rather than from the loop's own tally: a
    # match links both sides, so the candidate rows updated along the
    # way are linked too without ever being the loop's current person.
    cursor.execute("SELECT count(*) FROM persons WHERE global_person_id IS NOT NULL")
    persons_linked = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM global_persons")
    identities_created = cursor.fetchone()[0]

    return {
        "persons_total": len(persons),
        "persons_unlinked": persons_unlinked,
        "identities_deleted": identities_deleted,
        "persons_linked": persons_linked,
        "identities_created": identities_created,
    }
