"""Parses FaceEmbedding and VoiceEmbedding rows.

Two embedding storage patterns show up across DUUI pipelines:

  1. The identity FS (FaceIdentity/VoiceIdentity) directly carries
     `.person`, `.model`, and a raw embedding vector under
     `.embeddings`.
  2. The identity FS only carries a string id (`faceId`/`voiceId`) and
     a *reference* to a separate Embedding FeatureStructure
     (`org.texttechnologylab.uima.type.Embedding`) that holds the real
     `.embedding` vector and a `.ModelReference` -- confirmed in the
     real Bundestag video-emotion CAS. In this pattern, person
     linkage is string-based and resolved via person_resolution
     using the face_id/voice_id -> person_id maps built in person.py.

Both patterns are handled so this keeps working regardless of which
DUUI component version produced the CAS.
"""

from ..cas.views import select_across_views
from ..cas.types import TYPES
from ..cas.person_resolution import (
    resolve_person_id_via_face_fs,
    resolve_person_id_via_voice_fs,
)
from ..cas.typesystem import as_list, get_xmi_id


def _to_pgvector_literal(embedding_repr):
    """
    Convert a raw embedding representation into the text literal
    format pgvector expects on INSERT: `[v1,v2,v3]` -- bracketed,
    comma-separated. cassis hands back a bare space-separated string
    (or a plain sequence of numbers) from the underlying UIMA feature,
    which pgvector's input parser rejects outright.
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


def _resolve_embedding_rows(identity_fs):
    """
    Normalizes the different shapes `.embeddings` can take into a list
    of (embedding_id, model_id, embedding_repr) tuples -- one per
    underlying Embedding FS when `.embeddings` references one or more
    separate Embedding annotations (a FaceIdentity can legitimately
    link several, e.g. one per detection over time: "988 990"), or a
    single tuple keyed on the identity FS's own id when `.embeddings`
    already holds the raw vector directly (older pipeline shape).
    """
    embeddings_value = getattr(identity_fs, "embeddings", None)
    if embeddings_value is None:
        return []

    items = as_list(embeddings_value)

    if items and all(hasattr(item, "embedding") for item in items):
        # Every item is a real Embedding FeatureStructure: dereference
        # each one into its own row so none are silently dropped.
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


def _parse_embeddings(cas, cursor, uima_type, table_name, resolve_person_id, context):
    """
    Face and voice embeddings differ only in which identity type they
    come from, which resolver turns that identity into a person_id, and
    which table they land in -- everything else (the `.embeddings`
    shapes, the model reference, the pgvector literal) is identical, so
    one helper covers both (same pattern as parsers/detection.py).
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
                INSERT INTO {table_name} (video_id, embedding_id, person_id, model_id, embedding)
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


def parse(cas, cursor, context):
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
