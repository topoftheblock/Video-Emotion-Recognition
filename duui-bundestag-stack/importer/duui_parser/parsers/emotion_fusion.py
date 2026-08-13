"""
Multimodal emotion fusion.

`fused_emotions` has always existed in the schema for "a combined
emotion signal", but the only thing that ever populated it was an
`aggregatedFrom` feature on the CAS's own Emotion FS (see
parsers/emotion.py) -- which the real Bundestag CAS never sets, so the
table stayed permanently empty. This step computes an actual fusion
ourselves: after every base_emotions row for this video has been
inserted (it runs last), it walks every sentence segment and, for
whichever of audio/video/text has data for that sentence, combines
them into one multimodal reading.

Method (`fusion_method = 'mean-valence-arousal-v1'`, so a smarter
method can be introduced later without ambiguity about which rows used
which approach): average valence/arousal within each available
modality first (a sentence has one audio/text reading but many
per-frame video readings), then average those per-modality values
across modalities. `dominant_label` is taken from whichever modality
had the largest valence/arousal magnitude, as a cheap best-effort
proxy for "most emotionally salient modality" -- not a trained
classifier decision.

`target_modality` is constrained by the schema to one of
('multimodal', 'video-aggregated', 'text-aggregated') -- there is no
'audio-aggregated' bucket, so a sentence with only audio data (or any
mix that includes audio) is filed under 'multimodal'.
"""

from ..config import ENABLE_EMOTION_FUSION

_FUSION_METHOD = "mean-valence-arousal-v1"


def _text_signal(cursor, video_id, begin_offset, end_offset):
    cursor.execute(
        """
        SELECT emotion_id, valence, arousal, dominant_label
        FROM base_emotions
        WHERE video_id = %s AND modality = 'text' AND valence IS NOT NULL
          AND begin_offset >= %s AND end_offset <= %s
        """,
        (video_id, begin_offset, end_offset),
    )
    return cursor.fetchall()


def _audio_signal(cursor, video_id, start_time, end_time):
    cursor.execute(
        """
        SELECT emotion_id, valence, arousal, dominant_label
        FROM base_emotions
        WHERE video_id = %s AND modality = 'audio' AND valence IS NOT NULL
          AND start_time <= %s AND end_time >= %s
        """,
        (video_id, end_time, start_time),
    )
    return cursor.fetchall()


def _video_signal(cursor, video_id, person_id, start_time, end_time):
    if person_id is None:
        # Can't reliably attribute frames to this sentence's speaker
        # without a person link -- skip rather than guessing across
        # whoever happens to be on screen.
        return []
    cursor.execute(
        """
        SELECT emotion_id, valence, arousal, dominant_label
        FROM base_emotions
        WHERE video_id = %s AND modality = 'video' AND person_id = %s
          AND valence IS NOT NULL AND start_time BETWEEN %s AND %s
        """,
        (video_id, person_id, start_time, end_time),
    )
    return cursor.fetchall()


def _average_modality(rows):
    """Collapse N rows from one modality into one (valence, arousal,
    dominant_label, [emotion_ids]) -- dominant_label from the single
    highest-magnitude row among them."""
    if not rows:
        return None
    valences = [r[1] for r in rows]
    arousals = [r[2] for r in rows]
    best = max(rows, key=lambda r: (r[1] or 0) ** 2 + (r[2] or 0) ** 2)
    return (
        sum(valences) / len(valences),
        sum(arousals) / len(arousals),
        best[3],
        [r[0] for r in rows],
    )


def _fuse_segment(cursor, video_id, segment_id, start_time, end_time, begin_offset, end_offset, person_id):
    per_modality = {}
    text = _average_modality(_text_signal(cursor, video_id, begin_offset, end_offset))
    if text:
        per_modality["text"] = text
    audio = _average_modality(_audio_signal(cursor, video_id, start_time, end_time))
    if audio:
        per_modality["audio"] = audio
    video = _average_modality(_video_signal(cursor, video_id, person_id, start_time, end_time))
    if video:
        per_modality["video"] = video

    if not per_modality:
        return

    if set(per_modality) == {"video"}:
        target_modality = "video-aggregated"
    elif set(per_modality) == {"text"}:
        target_modality = "text-aggregated"
    else:
        # Includes "only audio" -- the schema has no dedicated bucket
        # for that, see module docstring.
        target_modality = "multimodal"

    valence = sum(v[0] for v in per_modality.values()) / len(per_modality)
    arousal = sum(v[1] for v in per_modality.values()) / len(per_modality)
    dominant_label = max(per_modality.values(), key=lambda v: (v[0] or 0) ** 2 + (v[1] or 0) ** 2)[2]
    source_emotion_ids = [eid for v in per_modality.values() for eid in v[3]]

    # fused_id reuses segment_id (stable within this CAS's own xmi:id
    # space -- see parsers/__init__.py's ordering note on why every
    # other table's PK does the same) so re-running the parser on the
    # same file updates this fusion instead of duplicating it.
    fused_id = segment_id
    cursor.execute(
        """
        INSERT INTO fused_emotions (fused_id, video_id, person_id, fusion_method, target_modality, start_time, end_time, valence, arousal, dominant_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fused_id) DO UPDATE SET
            video_id = EXCLUDED.video_id, person_id = EXCLUDED.person_id,
            fusion_method = EXCLUDED.fusion_method, target_modality = EXCLUDED.target_modality,
            start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time,
            valence = EXCLUDED.valence, arousal = EXCLUDED.arousal,
            dominant_label = EXCLUDED.dominant_label
        """,
        (fused_id, video_id, person_id, _FUSION_METHOD, target_modality, start_time, end_time, valence, arousal, dominant_label),
    )

    for source_emotion_id in source_emotion_ids:
        cursor.execute(
            """
            INSERT INTO emotion_fusion_references (fused_id, source_emotion_id)
            VALUES (%s, %s)
            ON CONFLICT (fused_id, source_emotion_id) DO NOTHING
            """,
            (fused_id, source_emotion_id),
        )


def parse(cas, cursor, context):
    if not ENABLE_EMOTION_FUSION:
        return

    video_id = context.get("global_video_id")
    if video_id is None:
        return

    cursor.execute(
        """
        SELECT segment_id, start_time, end_time, begin_offset, end_offset, person_id
        FROM segments WHERE video_id = %s AND kind = 'sentence'
        """,
        (video_id,),
    )
    sentences = cursor.fetchall()

    for segment_id, start_time, end_time, begin_offset, end_offset, person_id in sentences:
        if start_time is None or end_time is None:
            continue
        _fuse_segment(cursor, video_id, segment_id, start_time, end_time, begin_offset, end_offset, person_id)
