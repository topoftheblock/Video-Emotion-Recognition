"""Reads the face and voice embeddings that identify a person.

Two storage patterns appear across DUUI pipelines:

1. The identity structure carries `.person`, `.model` and a raw vector
   under `.embeddings` directly.
2. The identity structure carries only a string id and a *reference* to
   a separate Embedding structure holding the real `.embedding` vector
   and a `.ModelReference` — the shape confirmed in the real CAS. Here
   the person link is string-based, and is resolved through
   `cas/person_resolution.py` using the maps `person.py` built.

Both are handled, so this keeps working whichever component version
produced the CAS.
"""

from collections.abc import Callable
from typing import Any

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.person_resolution import (
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from ..cas.types import TYPES
from ..cas.typesystem import as_list, get_xmi_id
from ..cas.views import select_across_views


def _to_pgvector_literal(embedding_repr: Any) -> str | None:
    """Convert a raw vector into the literal pgvector expects.

    That is `[v1,v2,v3]`: bracketed and comma-separated. cassis hands
    back a space-separated string, or a plain sequence of numbers, from
    the underlying UIMA feature — which pgvector's input parser rejects
    outright.

    Args:
        embedding_repr: The vector as cassis returned it.

    Returns:
        The literal, or None when there is no vector.
    """
    if embedding_repr is None:
        return None
    if isinstance(embedding_repr, str):
        values = embedding_repr.split()
    else:
        values = list(embedding_repr)
    if not values:
        return None
    return "[" + ",".join(str(v) for v in values) + "]"


def _resolve_embedding_rows(identity_fs: Any) -> list[tuple]:
    """Normalize the shapes `.embeddings` takes into one row list.

    One row per underlying Embedding structure when `.embeddings`
    references separate Embedding annotations — a FaceIdentity may
    legitimately link several, one per detection over time — or a
    single row keyed on the identity's own id when `.embeddings`
    already holds the raw vector, which is the older shape.

    Args:
        identity_fs: The FaceIdentity or VoiceIdentity structure.

    Returns:
        `(embedding_id, model_id, vector)` triples.
    """
    embeddings_value = getattr(identity_fs, "embeddings", None)
    if embeddings_value is None:
        return []

    items = as_list(embeddings_value)

    if items and all(hasattr(item, "embedding") for item in items):
        # Every item is a real Embedding structure: dereference each
        # into its own row, so none is silently dropped.
        return [
            (
                get_xmi_id(item),
                get_xmi_id(getattr(item, "ModelReference", None)),
                getattr(item, "embedding", None),
            )
            for item in items
        ]

    # Fallback: `.embeddings` already held raw vector data directly.
    return [(get_xmi_id(identity_fs), None, str(embeddings_value))]


def _parse_embeddings(
    cas: Cas,
    cursor: Cursor,
    uima_type: str,
    table_name: str,
    resolve_person_id: Callable[[Any, dict], int | None],
    context: dict,
) -> None:
    """Insert every embedding of one kind into one table.

    Face and voice embeddings differ only in the identity type they
    come from, the resolver that turns it into a person, and the table
    they land in. The `.embeddings` shapes, the model reference and the
    pgvector literal are identical, so one helper covers both.

    `table_name` is interpolated into the statement rather than passed
    as a parameter, which a table name cannot be. Both call sites below
    pass a literal, so no external value reaches it.
    """
    video_id = context.get("global_video_id")
    # The model references in this CAS are xmi:ids; `models` is keyed
    # by (name, version, source) and numbered by the database, so they
    # have to be translated through the map parsers/model.py built.
    model_ids = context.get("model_id_by_xmi_id", {})

    for item in select_across_views(cas, uima_type):
        person_id = resolve_person_id(item, context)
        own_model_id = get_xmi_id(getattr(item, "model", None))

        for embedding_id, derived_model_id, embedding_repr in _resolve_embedding_rows(
            item
        ):
            if embedding_id is None:
                continue
            cursor.execute(
                f"""
                INSERT INTO {table_name}
                    (video_id, embedding_id, person_id, model_id,
                     embedding)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (video_id, embedding_id) DO NOTHING
                """,
                (
                    video_id,
                    embedding_id,
                    person_id,
                    model_ids.get(own_model_id or derived_model_id),
                    _to_pgvector_literal(embedding_repr),
                ),
            )


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert this video's face and voice embeddings.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    _parse_embeddings(
        cas,
        cursor,
        TYPES["face_identity"],
        "face_embeddings",
        resolve_person_id_via_face_fs,
        context,
    )
    _parse_embeddings(
        cas,
        cursor,
        TYPES["voice_identity"],
        "voice_embeddings",
        resolve_person_id_via_voice_fs,
        context,
    )
