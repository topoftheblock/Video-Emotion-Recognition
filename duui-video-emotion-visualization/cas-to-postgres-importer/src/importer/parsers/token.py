"""Parses LinguisticToken rows from DiarizedAudioToken annotations.

Field names vary across pipeline versions: some store the token text
under `.word`, others (confirmed in the real Bundestag CAS) under
`.value`. `pos_tag`/`ner_label`/`segment` are also not always present
-- when absent they're simply left NULL rather than causing an error.
"""

from ..cas.views import select_across_views
from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id


def _resolve_word(token):
    if hasattr(token, "value") and token.value is not None:
        return token.value
    if hasattr(token, "word") and token.word is not None:
        return token.word
    return token.get_covered_text()


def parse(cas, cursor, context):
    video_id = context.get("global_video_id")

    for token in select_across_views(cas, TYPES["diarized_audio_token"]):
        token_id = get_xmi_id(token)
        cursor.execute(
            """
            INSERT INTO linguistic_tokens (token_id, video_id, segment_id, start_time, end_time, begin_offset, end_offset, word, pos_tag, ner_label)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (video_id, token_id) DO NOTHING
            """,
            (
                token_id,
                video_id,
                get_xmi_id(getattr(token, "segment", None)),
                getattr(token, "timeStart", None),
                getattr(token, "timeEnd", None),
                token.begin,
                token.end,
                _resolve_word(token),
                getattr(token, "pos_tag", None),
                getattr(token, "ner_label", None),
            ),
        )
