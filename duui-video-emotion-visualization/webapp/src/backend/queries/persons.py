"""Reading the people who have been linked across videos."""

from typing import Any

from ..db import query


def list_global_clusters() -> list[dict[str, Any]]:
    """Return each global person, with the people making it up.

    Only people the linker has actually linked appear. Someone with no
    cross-video match does not, because the linker creates a global
    person only when it finds a match and then assigns both sides — so
    a global person always has at least two members. This query does
    not filter for that itself; it is a property of what wrote the rows.

    Expect nothing at all until that job has been run. It is a separate
    container, never part of `docker compose up`, so importing videos
    alone leaves every `global_person_id` NULL.

    Returns:
        One entry per global person, each with its members and the
        video and label each member came from.
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

    clusters: dict[int, dict[str, Any]] = {}
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
