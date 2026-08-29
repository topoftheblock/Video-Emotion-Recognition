"""Reads transcript tokens from DiarizedAudioToken annotations.

Field names vary between pipeline versions: some store the token text
under `.word`, others — confirmed in the real CAS — under `.value`. The
part-of-speech tag, named-entity label and segment reference are also
not always present, and are left NULL when absent rather than treated
as an error.
"""

from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def _resolve_word(token: Any) -> str | None:
    """Return the token's text, from whichever field carries it."""
    if hasattr(token, "value") and token.value is not None:
        return token.value
    if hasattr(token, "word") and token.word is not None:
        return token.word
    return token.get_covered_text()


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's transcript tokens.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    video_id = context.get("global_video_id")

    for token in select_across_views(cas, TYPES["diarized_audio_token"]):
        token_id = get_xmi_id(token)
        cursor.execute(
            """
            INSERT INTO linguistic_tokens
                (token_id, video_id, segment_id, start_time, end_time,
                 begin_offset, end_offset, word, pos_tag, ner_label)
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
