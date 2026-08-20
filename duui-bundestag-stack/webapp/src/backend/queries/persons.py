"""Cross-video person identity."""

from ..db import query


def list_global_clusters():
    """
    Every global_persons cluster that
    global-identity-linker/src/identity/linking.py
    has linked two or more video-local `persons` rows into, with which
    video/clip_label each member came from. A person with no
    cross-video match (still the common case -- see linking.py's
    docstring) simply doesn't appear here; this is specifically "who
    spans videos", not "everyone".

    Expect nothing at all until that job has been run: it is a separate
    container that is never part of `docker compose up`, so importing
    videos alone leaves every `global_person_id` NULL.
    """
    rows = query(
        """
        SELECT gp.global_person_id, gp.real_name,
               p.person_id, p.video_id, p.clip_label,
               p.audio_video_match_score, p.global_person_match_score,
               v.filename AS video_filename
        FROM global_persons gp
        JOIN persons p ON p.global_person_id = gp.global_person_id
        JOIN videos v ON v.video_id = p.video_id
        ORDER BY gp.global_person_id, v.processed_at
        """
    )

    clusters = {}
    for row in rows:
        cluster = clusters.setdefault(
            row["global_person_id"],
            {
                "global_person_id": row["global_person_id"],
                "real_name": row["real_name"],
                "members": [],
            },
        )
        cluster["members"].append(
            {
                "person_id": row["person_id"],
                "video_id": row["video_id"],
                "video_filename": row["video_filename"],
                "clip_label": row["clip_label"],
                "audio_video_match_score": row["audio_video_match_score"],
                "global_person_match_score": row["global_person_match_score"],
            }
        )
    return list(clusters.values())
