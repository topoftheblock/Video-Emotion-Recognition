"""Group people across videos into global persons, by distance.

For every person without a `global_person_id`, this finds the closest
person in a *different* video by cosine distance between embedding
centroids, and either joins that person's existing global person or
creates one shared by both.

**Nothing else writes `persons.global_person_id`.** No shipped
typesystem defines a `GlobalPerson` annotation and no parser sets the
column, so without this job every video's people stay isolated from one
another.

The whole corpus is recomputed at once — existing global persons are
cleared first, then rebuilt — so the result depends only on what is in
the database and not on the order it arrived in. That is why the job is
run explicitly rather than as a step of importing.

**The result is a similarity heuristic, not a verified identity.** Treat
a shared `global_person_id` as "probably the same person". Each person's
nearest cross-video distance is kept in
`persons.global_person_match_score` so the strength of a grouping can be
inspected, and the thresholds in `config.py` have no derivation recorded
in this repository — retune them against known duplicates before relying
on the groupings for anything beyond suggestions.
"""

from collections.abc import Callable

from psycopg2.extensions import cursor as Cursor

from .config import (
    GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD,
    GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD,
)

# A person, everywhere in this module.
Person = tuple[int, int]

# One centroid per person per modality, rather than a nearest-neighbour
# search across individual embeddings: a person has one embedding per
# detection frame, and the signal is their face across those frames
# rather than any single one. pgvector averages the vector type
# directly.
#
# Materialised into a temp table once per run rather than recomputed as
# a CTE inside each lookup, because a recompute does one lookup per
# person in the corpus and each would otherwise rescan the whole
# embeddings table.
#
# Keyed by (video_id, person_id) throughout, never person_id alone: a
# person_id is an xmi:id, unique only within its own CAS, so the same
# value names different people in different videos. See
# docs/database.md.
_BUILD_CENTROIDS_SQL = """
CREATE TEMP TABLE {temp_table} AS
SELECT e.video_id, e.person_id, avg(e.embedding) AS centroid
FROM {source_table} e
WHERE e.person_id IS NOT NULL
GROUP BY e.video_id, e.person_id
"""

# `global_person_id` is read from `persons` rather than from the temp
# table: the loop assigns ids as it goes, and a candidate matched
# earlier in the same run must be seen with the id it has just been
# given, not the NULL it started with.
#
# `c2.video_id != c1.video_id` is enough to exclude the person
# themselves, since a person belongs to exactly one video.
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

# (temp table, the embeddings table it is built from, distance
# threshold).
#
# Order matters: face is tried first and voice is the fallback, so a
# person with no usable face embedding can still be linked by voice.
#
# Schema-qualified with `pg_temp` deliberately. Unqualified, both the
# DROP and the lookups would act on a permanent table of the same name
# if one ever existed, and dropping a real table is a bad way to
# discover that.
_MODALITIES = (
    (
        "pg_temp.face_centroids",
        "face_embeddings",
        GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD,
    ),
    (
        "pg_temp.voice_centroids",
        "voice_embeddings",
        GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD,
    ),
)


def clear_global_persons(cursor: Cursor) -> tuple[int, int]:
    """Delete every global person and unlink every person from one.

    `global_person_match_score` is cleared with `global_person_id`, both
    being this job's output. `audio_video_match_score` belongs to the
    importer and is left alone.

    Both statements are issued explicitly rather than relying on the
    foreign key's ON DELETE SET NULL, which would cover the unlinking:
    the counts returned here are what the caller reports, and they
    cannot be collected from a cascade.

    Returns:
        The number of persons that had been linked, and the number of
            global
        persons deleted.
    """
    cursor.execute("SELECT count(*) FROM persons WHERE global_person_id IS NOT NULL")
    persons_unlinked = cursor.fetchone()[0]

    cursor.execute(
        "UPDATE persons SET global_person_id = NULL, global_person_match_score = NULL"
    )

    cursor.execute("DELETE FROM global_persons")
    global_persons_deleted = cursor.rowcount

    return persons_unlinked, global_persons_deleted


def build_centroids(cursor: Cursor) -> None:
    """Build the face and voice centroid temp tables this run reads.

    Temp tables last for the session, so they disappear when the
    connection closes. The DROP lets this be called twice on one
    connection instead of failing on the second build.
    """
    for temp_table, source_table, _threshold in _MODALITIES:
        cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")
        cursor.execute(
            _BUILD_CENTROIDS_SQL.format(
                temp_table=temp_table, source_table=source_table
            )
        )
        # A freshly created temp table has no statistics, so the planner
        # assumes a token row count and can choose a nested loop that
        # does not survive a real corpus.
        cursor.execute(f"ANALYZE {temp_table}")


def _best_cross_video_match(
    cursor: Cursor, person: Person, temp_table: str, threshold: float
) -> tuple[Person, int | None, float] | None:
    """Find the closest person in another video, if one is close enough.

    Args:
        person: The person to match.
        temp_table: The centroid table to search, from `_MODALITIES`.
        threshold: Maximum cosine distance to accept. Lower is more
            similar.

    Returns:
        The candidate, the global person it already belongs to if any,
            and the
        distance between them. None when there is no candidate, or the
            closest
        one is beyond `threshold`.
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


def _create_global_person(cursor: Cursor) -> int:
    """Create an empty global person and return its id."""
    cursor.execute(
        "INSERT INTO global_persons (real_name) VALUES (NULL) "
        "RETURNING global_person_id"
    )
    return cursor.fetchone()[0]


def _assign_global_person(
    cursor: Cursor, person: Person, global_person_id: int
) -> None:
    """Point one person at a global person."""
    video_id, person_id = person
    cursor.execute(
        "UPDATE persons SET global_person_id = %s "
        "WHERE video_id = %s AND person_id = %s",
        (global_person_id, video_id, person_id),
    )


def _current_global_person_id(cursor: Cursor, person: Person) -> int | None:
    """Read a person's global person id as it stands right now."""
    video_id, person_id = person
    cursor.execute(
        "SELECT global_person_id FROM persons WHERE video_id = %s AND person_id = %s",
        (video_id, person_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def link_person(cursor: Cursor, person: Person) -> int | None:
    """Link one person to a global person, if a match is close enough.

    Face is tried first, then voice. A match to someone who already has
    a global person joins it; a match to someone who does not creates
    one and assigns it to both.

    `build_centroids` must have run on this cursor first.

    Returns:
        The global person id this person ended up with, or None if it
            stays
        unlinked.
    """
    # Read the current value rather than trusting one taken before the
    # loop: an earlier person in this run may have matched this one and
    # already assigned it an id, and linking it again would split a
    # group that was just joined.
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
    global_id = (
        candidate_global_id
        if candidate_global_id is not None
        else _create_global_person(cursor)
    )

    _assign_global_person(cursor, person, global_id)
    if candidate_global_id is None:
        _assign_global_person(cursor, candidate_person, global_id)

    return global_id


def _write_match_scores(cursor: Cursor) -> None:
    """Record how close each person came to anyone in another video.

    For a person with at least one centroid, the score is the smallest
    cosine distance to any person in a different video, taking the
    better of face and voice. A person with no embeddings in either
    modality is left NULL.

    Written for every person, linked or not, so an unlinked person can
    be inspected for how near the threshold it fell. Being a pure
    function of the centroids, it does not depend on the order persons
    were linked in and is identical on every recompute.
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


def recompute_global_persons(
    cursor: Cursor, progress: Callable[[int, int], None] | None = None
) -> dict[str, int]:
    """Clear every global person and rebuild them corpus-wide.

    Persons are walked in `(video_id, person_id)` order so that a run is
    reproducible. Since every person starts unlinked, that order decides
    only which side of a pair creates the shared row, not who ends up
    grouped with whom.

    Takes a cursor rather than opening its own connection, because the
    clear and the rebuild have to be one transaction: a failure part way
    through must leave the previous groupings intact rather than a
    corpus that has been cleared and not rebuilt.

    Args:
        progress: Called with (index, total) after each person, for
            reporting.

    Returns:
        Counts of persons seen, previously linked, and linked now, along
            with
        global persons deleted and created.
    """
    persons_unlinked, global_persons_deleted = clear_global_persons(cursor)

    build_centroids(cursor)

    cursor.execute(
        "SELECT video_id, person_id FROM persons ORDER BY video_id, person_id"
    )
    persons = cursor.fetchall()

    linked_ids = set()
    for index, person in enumerate(persons, start=1):
        global_id = link_person(cursor, person)
        if global_id is not None:
            linked_ids.add(global_id)
        if progress is not None:
            progress(index, len(persons))

    _write_match_scores(cursor)

    # Counted from `persons` rather than from the loop's own tally: a
    # match links both sides, so a candidate updated along the way is
    # linked without ever having been the loop's current person.
    cursor.execute("SELECT count(*) FROM persons WHERE global_person_id IS NOT NULL")
    persons_linked = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM global_persons")
    identities_created = cursor.fetchone()[0]

    return {
        "persons_total": len(persons),
        "persons_unlinked": persons_unlinked,
        "global_persons_deleted": global_persons_deleted,
        "persons_linked": persons_linked,
        "identities_created": identities_created,
    }
