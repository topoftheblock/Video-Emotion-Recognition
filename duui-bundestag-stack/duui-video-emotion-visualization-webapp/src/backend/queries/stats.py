"""
The fixed (not LLM-written) emotion statistics behind the "Emotion
insights" panel.

Deliberately plain SQL rather than routed through the NL->SQL agent,
both for speed/determinism and so there's always at least a few
analyses available even with the query agent unconfigured. Computed on
demand, not cached/written back to the DB -- see README "Emotion
statistics" for why.
"""

from ..db import query


def emotion_distribution(video_id):
    """Stat 1: how often each dominant_label occurred, per modality."""
    return query(
        """
        SELECT modality, dominant_label, count(*) AS n
        FROM base_emotions
        WHERE video_id = %s AND dominant_label IS NOT NULL
        GROUP BY modality, dominant_label
        ORDER BY modality, n DESC
        """,
        (video_id,),
    )


def person_emotion_averages(video_id):
    """Stat 2: mean valence/arousal per person, per modality."""
    return query(
        """
        SELECT be.person_id, COALESCE(p.clip_label, 'person ' || be.person_id::text) AS clip_label,
               be.modality, avg(be.valence) AS avg_valence, avg(be.arousal) AS avg_arousal, count(*) AS n
        FROM base_emotions be
        LEFT JOIN persons p ON p.person_id = be.person_id
        WHERE be.video_id = %s AND be.person_id IS NOT NULL AND be.valence IS NOT NULL
        GROUP BY be.person_id, p.clip_label, be.modality
        ORDER BY be.person_id, be.modality
        """,
        (video_id,),
    )


def modality_agreement(video_id):
    """
    Stat 3: of the sentences with both a text and a video emotion
    reading, what fraction agree on valence sign (both positive or
    both negative)? A single summary number, not per-sentence rows --
    see query_agent/schema_context.py's "Cross-modality label
    comparison" note for why this uses valence sign rather than
    comparing dominant_label strings across modalities directly.
    """
    rows = query(
        """
        WITH text_anchored AS (
            SELECT s.segment_id, s.start_time, s.end_time, s.person_id, te.valence AS text_valence
            FROM segments s
            JOIN base_emotions te
              ON te.video_id = s.video_id AND te.modality = 'text'
             AND te.begin_offset >= s.begin_offset AND te.end_offset <= s.end_offset
            WHERE s.kind = 'sentence' AND s.video_id = %s AND te.valence IS NOT NULL
        ),
        video_per_sentence AS (
            SELECT ta.segment_id, avg(ve.valence) AS video_valence
            FROM text_anchored ta
            JOIN base_emotions ve
              ON ve.video_id = %s AND ve.modality = 'video' AND ve.person_id = ta.person_id
             AND ve.start_time BETWEEN ta.start_time AND ta.end_time AND ve.valence IS NOT NULL
            GROUP BY ta.segment_id
        )
        SELECT count(*) AS n_compared,
               count(*) FILTER (WHERE sign(ta.text_valence) = sign(vp.video_valence)) AS n_agree
        FROM text_anchored ta
        JOIN video_per_sentence vp ON vp.segment_id = ta.segment_id
        """,
        (video_id, video_id),
    )
    n_compared = rows[0]["n_compared"] if rows else 0
    n_agree = rows[0]["n_agree"] if rows else 0
    return {
        "n_compared": n_compared,
        "n_agree": n_agree,
        "agreement_pct": round(100 * n_agree / n_compared, 1) if n_compared else None,
    }


def for_video(video_id):
    """All three stats, as the /api/stats/{video_id} payload."""
    return {
        "emotion_distribution": emotion_distribution(video_id),
        "person_averages": person_emotion_averages(video_id),
        "modality_agreement": modality_agreement(video_id),
    }
