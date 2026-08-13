"""Parses Segment rows: video Shots and audio SpeakerSentences."""

from ..cas_views import select_across_views
from ..config import TYPES
from ..typesystem import get_xmi_id


def _parse_shots(cas, cursor, conn, video_id):
    for shot in select_across_views(cas, TYPES["shot"]):
        segment_id = get_xmi_id(shot)
        cursor.execute(
            """
            INSERT INTO segments (segment_id, video_id, kind, seg_index, start_time, end_time, begin_offset, end_offset)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (segment_id) DO NOTHING
            """,
            (
                segment_id,
                video_id,
                "shot",
                getattr(shot, "shotIndex", None),
                getattr(shot, "timeStart", None),
                getattr(shot, "timeEnd", None),
                shot.begin,
                shot.end,
            ),
        )


def _resolve_sentence_person_id(sentence):
    if hasattr(sentence, "speakerSegment") and sentence.speakerSegment:
        voice = getattr(sentence.speakerSegment, "voice", None)
        if voice and getattr(voice, "person", None) is not None:
            return get_xmi_id(voice.person)
    return None


def _parse_sentences(cas, cursor, conn, video_id):
    for sentence in select_across_views(cas, TYPES["speaker_sentence"]):
        segment_id = get_xmi_id(sentence)
        person_id = _resolve_sentence_person_id(sentence)

        cursor.execute(
            """
            INSERT INTO segments (segment_id, video_id, kind, start_time, end_time, begin_offset, end_offset, person_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (segment_id) DO NOTHING
            """,
            (
                segment_id,
                video_id,
                "sentence",
                getattr(sentence, "timeStart", None),
                getattr(sentence, "timeEnd", None),
                sentence.begin,
                sentence.end,
                person_id,
            ),
        )


def parse(cas, cursor, conn, context):
    video_id = context.get("global_video_id")
    _parse_shots(cas, cursor, conn, video_id)
    _parse_sentences(cas, cursor, conn, video_id)
