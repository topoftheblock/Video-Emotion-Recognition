"""
DB-integration test for duui_parser/parsers/emotion_fusion.py -- same
rollback-based isolation as test_global_identity.py (see conftest.py).
"""

import pytest

from duui_parser.parsers import emotion_fusion

VIDEO_ID = 9_200_001
PERSON_ID = 9_200_101
SEGMENT_ID = 9_200_201
TEXT_EMOTION_ID = 9_200_301
AUDIO_EMOTION_ID = 9_200_302
VIDEO_EMOTION_ID_1 = 9_200_303
VIDEO_EMOTION_ID_2 = 9_200_304


def _insert_base_emotion(cursor, emotion_id, modality, start_time, end_time, begin_offset, end_offset, valence, arousal, label):
    cursor.execute(
        """
        INSERT INTO base_emotions
            (emotion_id, person_id, video_id, modality, granularity,
             start_time, end_time, begin_offset, end_offset, valence, arousal, dominant_label)
        VALUES (%s, %s, %s, %s, 'sentence', %s, %s, %s, %s, %s, %s, %s)
        """,
        (emotion_id, PERSON_ID, VIDEO_ID, modality, start_time, end_time, begin_offset, end_offset, valence, arousal, label),
    )


def test_fuses_all_three_modalities_for_a_sentence(db_cursor):
    db_cursor.execute("INSERT INTO videos (video_id, filename) VALUES (%s, %s)", (VIDEO_ID, "test.mp4"))
    db_cursor.execute(
        "INSERT INTO persons (person_id, video_id, clip_label) VALUES (%s, %s, %s)",
        (PERSON_ID, VIDEO_ID, "person_1"),
    )
    db_cursor.execute(
        """
        INSERT INTO segments (segment_id, video_id, kind, start_time, end_time, begin_offset, end_offset, person_id)
        VALUES (%s, %s, 'sentence', 0.0, 2.0, 0, 10, %s)
        """,
        (SEGMENT_ID, VIDEO_ID, PERSON_ID),
    )

    # text: anchored via begin/end offset overlap with the segment
    _insert_base_emotion(db_cursor, TEXT_EMOTION_ID, "text", None, None, 0, 10, 0.6, 0.2, "joy")
    # audio: anchored via time overlap with the segment
    _insert_base_emotion(db_cursor, AUDIO_EMOTION_ID, "audio", 0.0, 2.0, None, None, -0.2, 0.4, "sad")
    # video: two per-frame readings within the segment's time window,
    # for the same person -- averaged before being combined further.
    _insert_base_emotion(db_cursor, VIDEO_EMOTION_ID_1, "video", 0.5, 0.52, None, None, 0.0, 0.0, "Neutral")
    _insert_base_emotion(db_cursor, VIDEO_EMOTION_ID_2, "video", 1.0, 1.02, None, None, 0.4, -0.4, "Happiness")

    emotion_fusion.parse(None, db_cursor, {"global_video_id": VIDEO_ID})

    db_cursor.execute(
        "SELECT fused_id, target_modality, valence, arousal FROM fused_emotions WHERE video_id = %s",
        (VIDEO_ID,),
    )
    rows = db_cursor.fetchall()
    assert len(rows) == 1
    fused_id, target_modality, valence, arousal = rows[0]
    assert target_modality == "multimodal"  # audio present -> no dedicated bucket, see module docstring

    # text=0.6, audio=-0.2, video=avg(0.0, 0.4)=0.2 -> mean = 0.2
    assert valence == _approx(0.2)
    # text=0.2, audio=0.4, video=avg(0.0, -0.4)=-0.2 -> mean = 0.13333...
    assert arousal == _approx((0.2 + 0.4 - 0.2) / 3)

    db_cursor.execute("SELECT source_emotion_id FROM emotion_fusion_references WHERE fused_id = %s", (fused_id,))
    referenced = {row[0] for row in db_cursor.fetchall()}
    assert referenced == {TEXT_EMOTION_ID, AUDIO_EMOTION_ID, VIDEO_EMOTION_ID_1, VIDEO_EMOTION_ID_2}


def test_skips_sentence_with_no_emotion_data(db_cursor):
    other_video = VIDEO_ID + 1
    other_segment = SEGMENT_ID + 1
    db_cursor.execute("INSERT INTO videos (video_id, filename) VALUES (%s, %s)", (other_video, "empty.mp4"))
    db_cursor.execute(
        """
        INSERT INTO segments (segment_id, video_id, kind, start_time, end_time, begin_offset, end_offset)
        VALUES (%s, %s, 'sentence', 0.0, 2.0, 0, 10)
        """,
        (other_segment, other_video),
    )

    emotion_fusion.parse(None, db_cursor, {"global_video_id": other_video})

    db_cursor.execute("SELECT count(*) FROM fused_emotions WHERE video_id = %s", (other_video,))
    assert db_cursor.fetchone()[0] == 0


def _approx(value):
    return pytest.approx(value, abs=1e-9)
