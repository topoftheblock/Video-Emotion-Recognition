"""Parses Emotion annotations into four related tables:

- BaseEmotion            one row per Emotion annotation
- EmotionScore           nested per-label scores on an Emotion
- FusedEmotion           present only if the emotion aggregates others
- EmotionFusionReference links a FusedEmotion back to its source emotions

Person linkage: some pipelines set `.personId` directly on the
Emotion FS. The real Bundestag video-emotion CAS doesn't -- instead
the Emotion carries a `.reference` to the FaceDetection/PersonDetection
it was computed from, which in turn links to a PersonTrack -> FaceIdentity.
`_resolve_emotion_person_id` tries the direct attribute first and
falls back to walking that reference chain.
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..identity_resolution import (
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from ..typesystem import as_list, get_xmi_id


def _resolve_emotion_person_id(emotion, context):
    """
    `.personId` is used directly when present. Otherwise `.reference`
    is walked according to what it points to: a video detection
    (`reference.track.face`) or an audio/text SpeakerSentence
    (`reference.speakerSegment.voice`) -- both patterns are confirmed
    in the real Bundestag video-emotion CAS, one per modality.
    """
    person_id = getattr(emotion, "personId", None)
    if person_id is not None:
        return person_id

    reference = getattr(emotion, "reference", None)
    if reference is None:
        return None

    track = getattr(reference, "track", None)
    if track is not None:
        face = getattr(track, "face", None)
        person_id = resolve_person_id_via_face_fs(face, context)
        if person_id is not None:
            return person_id

    speaker_segment = getattr(reference, "speakerSegment", None)
    if speaker_segment is not None:
        voice = getattr(speaker_segment, "voice", None)
        person_id = resolve_person_id_via_voice_fs(voice, context)
        if person_id is not None:
            return person_id

    return None


def _dominant_label_from_scores(scores):
    """
    Best-effort recovery of a dominant label when the CAS doesn't set
    one directly (confirmed absent on the real Bundestag CAS's
    per-frame Emotion instances): pick the highest-scoring nested
    EmotionScore. `scores` must already be a plain list (see
    `as_list`) -- an FSArray wrapper would iterate incorrectly.
    """
    best_label, best_score = None, None
    for score in scores:
        raw_score = getattr(score, "score", None)
        if raw_score is None:
            continue
        try:
            numeric_score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if best_score is None or numeric_score > best_score:
            best_score = numeric_score
            best_label = getattr(score, "label", None)
    return best_label


def _insert_base_emotion(cursor, emotion, emotion_id, person_id, video_id, scores):
    """
    Uses DO UPDATE (not DO NOTHING) deliberately: `_insert_fused_emotion`
    below may need to pre-create a minimal stub row for a fusion
    source that hasn't been visited by the main parse loop yet, to
    satisfy the emotion_fusion_references FK constraint. DO UPDATE
    guarantees that whenever *this* emotion's own real data does get
    inserted -- whether that happens before or after such a stub was
    created -- it always overwrites the stub with the real values,
    rather than a DO NOTHING silently keeping an empty row forever.
    """
    cursor.execute(
        """
        INSERT INTO base_emotions (emotion_id, person_id, video_id, modality, granularity, start_time, end_time, begin_offset, end_offset, frame_index, x, y, w, h, valence, arousal, dominance, dominant_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (emotion_id) DO UPDATE SET
            person_id = EXCLUDED.person_id, video_id = EXCLUDED.video_id,
            modality = EXCLUDED.modality, granularity = EXCLUDED.granularity,
            start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time,
            begin_offset = EXCLUDED.begin_offset, end_offset = EXCLUDED.end_offset,
            frame_index = EXCLUDED.frame_index, x = EXCLUDED.x, y = EXCLUDED.y,
            w = EXCLUDED.w, h = EXCLUDED.h, valence = EXCLUDED.valence,
            arousal = EXCLUDED.arousal, dominance = EXCLUDED.dominance,
            dominant_label = EXCLUDED.dominant_label
        """,
        (
            emotion_id,
            person_id,
            video_id,
            getattr(emotion, "modality", None),
            getattr(emotion, "granularity", None),
            getattr(emotion, "timeStart", None),
            getattr(emotion, "timeEnd", None),
            emotion.begin,
            emotion.end,
            getattr(emotion, "frameIndex", None),
            getattr(emotion, "x", None),
            getattr(emotion, "y", None),
            getattr(emotion, "width", None),
            getattr(emotion, "height", None),
            getattr(emotion, "valence", None),
            getattr(emotion, "arousal", None),
            getattr(emotion, "dominance", None),
            getattr(emotion, "dominant_label", None) or _dominant_label_from_scores(scores),
        ),
    )


def _insert_emotion_scores(cursor, scores, emotion_id):
    for score in scores:
        cursor.execute(
            """
            INSERT INTO emotion_scores (emotion_id, label, score)
            VALUES (%s, %s, %s)
            ON CONFLICT (emotion_id, label) DO NOTHING
            """,
            (emotion_id, getattr(score, "label", None), getattr(score, "score", None)),
        )


def _insert_fused_emotion(cursor, emotion, emotion_id, person_id, video_id):
    """
    Returns the fused_id if this emotion aggregates other emotions of
    the *same* type via an `aggregatedFrom` feature, otherwise None.

    NOTE: this only covers same-type fusion. A separate, differently
    structured aggregation pattern (a distinct `annotation.Emotion`
    type wrapping `AnnotationComment` label/score pairs, used for
    text-based GoEmotions in the real Bundestag CAS) is handled by
    parsers/text_emotion.py instead, since it doesn't fit this shape.
    """
    aggregated_from = as_list(getattr(emotion, "aggregatedFrom", None))
    if not aggregated_from:
        return None

    # fused_id is always the same value as emotion_id (the fusion IS
    # this Emotion instance, just wearing a second "FusedEmotion" hat)
    # -- no DB round-trip needed to determine it.
    fused_id = emotion_id
    cursor.execute(
        """
        INSERT INTO fused_emotions (fused_id, video_id, person_id, fusion_method, target_modality, start_time, end_time, valence, arousal, dominant_label)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fused_id) DO NOTHING
        """,
        (
            fused_id,
            video_id,
            person_id,
            getattr(emotion, "fusion_method", None),
            getattr(emotion, "target_modality", None),
            getattr(emotion, "timeStart", None),
            getattr(emotion, "timeEnd", None),
            getattr(emotion, "valence", None),
            getattr(emotion, "arousal", None),
            getattr(emotion, "dominant_label", None),
        ),
    )

    for source_emotion in aggregated_from:
        source_emotion_id = get_xmi_id(source_emotion)
        # The source emotion may not have been visited by the main
        # parse loop yet (iteration order isn't guaranteed to reach it
        # before this fusion) -- pre-create a minimal stub so the FK
        # constraint below doesn't fail. `_insert_base_emotion`'s own
        # DO UPDATE ensures the source's real values win once its own
        # turn in the main loop comes up, instead of leaving this
        # stub in place forever.
        cursor.execute(
            """
            INSERT INTO base_emotions (emotion_id)
            VALUES (%s)
            ON CONFLICT (emotion_id) DO NOTHING
            """,
            (source_emotion_id,),
        )
        cursor.execute(
            """
            INSERT INTO emotion_fusion_references (fused_id, source_emotion_id)
            VALUES (%s, %s)
            ON CONFLICT (fused_id, source_emotion_id) DO NOTHING
            """,
            (fused_id, source_emotion_id),
        )

    return fused_id


def parse(cas, cursor, context):
    video_id = context.get("global_video_id")

    for emotion in select_across_views(cas, TYPES["emotion"]):
        emotion_id = get_xmi_id(emotion)
        person_id = _resolve_emotion_person_id(emotion, context)
        scores = as_list(getattr(emotion, "scores", None))

        _insert_base_emotion(cursor, emotion, emotion_id, person_id, video_id, scores)
        _insert_emotion_scores(cursor, scores, emotion_id)
        _insert_fused_emotion(cursor, emotion, emotion_id, person_id, video_id)
