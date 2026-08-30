"""The fixed emotion statistics, served by `/api/stats/{video_id}`.

Plain SQL rather than anything routed through the query agent, so these
are fast, deterministic, and available even when the agent is
unconfigured. Computed on demand and never written back.

All three are cross-cutting: they compare modalities and people against
each other, which is not what the webapp's per-modality panels do, so
nothing in the frontend reads them. The endpoint stays because it is
the one analysis surface needing neither an LLM nor hand-written SQL
from the caller.
"""

from typing import Any

from ..db import query

Row = dict[str, Any]


def emotion_distribution(video_id: int) -> list[Row]:
    """Count how often each dominant label occurred, per series.

    Grouped by *series* rather than by modality, because
    `modality='text'` carries the output of two annotators at once: a
    reading that is on the timeline, over a small label set, and a
    GoEmotions reading that is not. There is one of each per sentence,
    so grouping by modality alone counts every sentence twice and can
    report a label more often than the video has sentences.

    `modality` is still returned alongside, so a caller that only cares
    about the modality can group the two text series back together
    knowingly.
    """
    return query(
        """
        SELECT series, modality, dominant_label, count(*) AS n
        FROM (
            SELECT modality, dominant_label,
                   CASE WHEN modality = 'text' AND start_time IS NULL
                        THEN 'text (raw GoEmotions)' ELSE modality END AS series
            FROM base_emotions
            WHERE video_id = %s AND dominant_label IS NOT NULL
        ) labeled
        GROUP BY series, modality, dominant_label
        ORDER BY series, n DESC
        """,
        (video_id,),
    )


def person_emotion_averages(video_id: int) -> list[Row]:
    """Average valence and arousal per person, per modality."""
    return query(
        """
        SELECT be.person_id,
               COALESCE(p.clip_label, 'person ' || be.person_id::text) AS clip_label,
               be.modality,
               avg(be.valence) AS avg_valence,
               avg(be.arousal) AS avg_arousal,
               count(*) AS n
        FROM base_emotions be
        -- Both halves of the key: person_id alone is a per-video
        -- number, so joining on it would fan every reading out across
        -- every video that happens to have a person with that id.
        LEFT JOIN persons p ON p.video_id = be.video_id AND p.person_id = be.person_id
        WHERE be.video_id = %s AND be.person_id IS NOT NULL AND be.valence IS NOT NULL
        GROUP BY be.person_id, p.clip_label, be.modality
        ORDER BY be.person_id, be.modality
        """,
        (video_id,),
    )


def modality_agreement(video_id: int) -> dict[str, Any]:
    """Measure how often text and video agree on a sentence's valence.

    Of the sentences carrying both a text and a video reading, what
    fraction agree on the sign of valence — both positive, or both
    negative. One summary number, not per-sentence rows.

    Compared on valence sign rather than on `dominant_label`, because
    the label vocabularies are model-native and differ by modality, so
    the labels are not comparable across them; valence is.
    """
    rows = query(
        """
        WITH text_anchored AS (
            SELECT s.segment_id, s.start_time, s.end_time, s.person_id,
                   te.valence AS text_valence
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
              ON ve.video_id = %s AND ve.modality = 'video'
             AND ve.person_id = ta.person_id
             AND ve.start_time BETWEEN ta.start_time AND ta.end_time
             AND ve.valence IS NOT NULL
            GROUP BY ta.segment_id
        )
        SELECT count(*) AS n_compared,
               count(*) FILTER (
                   WHERE sign(ta.text_valence) = sign(vp.video_valence)
               ) AS n_agree
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


def for_video(video_id: int) -> dict[str, Any]:
    """Return all three statistics, as the endpoint's payload."""
    return {
        "emotion_distribution": emotion_distribution(video_id),
        "person_averages": person_emotion_averages(video_id),
        "modality_agreement": modality_agreement(video_id),
    }
