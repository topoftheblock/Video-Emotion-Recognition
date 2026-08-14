"""Cross-video person identity."""

from ..db import query


def list_global_clusters():
    """
    Every global_persons cluster that
    duui-video-emotion-cas-to-postgres/src/main/parsers/global_identity.py
    has linked two or more video-local `persons` rows into, with which
    video/clip_label each member came from. A person with no
    cross-video match (still the common case -- see global_identity.py's
    docstring) simply doesn't appear here; this is specifically "who
    spans videos", not "everyone".
    """
    rows = query(
        """
        SELECT gp.global_person_id, gp.real_name,
               p.person_id, p.video_id, p.clip_label, p.match_score,
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
                "match_score": row["match_score"],
            }
        )
    return list(clusters.values())
