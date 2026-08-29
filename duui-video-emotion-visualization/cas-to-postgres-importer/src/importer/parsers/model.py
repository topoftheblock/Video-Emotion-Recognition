"""Reads the models that produced the annotations.

The bare `org.texttechnologylab.annotation.MetaData` is the common
supertype of both the generic `model.MetaData` and the
`model.HuggingfaceMetaData` that transformer-based components use. The
latter carries the same name, version and source features plus extras,
such as HuggingfaceVersion, that the schema has no column for and which
are therefore not stored. Since `select` includes subtype instances,
selecting the bare type alone covers every model row.

`models` is the one table not keyed by `(video_id, xmi:id)`. A model is
corpus-wide — the same face model processes every video — so it is
keyed by what identifies it, `(name, version, source)`, and the row is
shared between videos instead of duplicated per import. The database
therefore assigns `model_id`, and this step records the mapping from
`xmi:id` in the context, so `embedding.py` can translate the model
references its annotations carry.
"""

from cassis import Cas
from psycopg2.extensions import cursor as Cursor

from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id
from ..cas.views import select_across_views


def parse(cas: Cas, cursor: Cursor, context: dict) -> None:
    """Insert a row per model, recording its assigned id in the context.

    Args:
        cas: The loaded CAS.
        cursor: An open cursor, inside the import's transaction.
        context: The shared context, threaded through every step.
    """
    model_ids = context.setdefault("model_id_by_xmi_id", {})

    for metadata in select_across_views(cas, TYPES["model_meta_data"]):
        cursor.execute(
            """
            INSERT INTO models (name, version, source)
            VALUES (%s, %s, %s)
            -- DO UPDATE, not DO NOTHING: an idempotent no-op write is
            -- what makes RETURNING give back the existing row's id
            -- rather than nothing at all on the second import.
            ON CONFLICT (name, version, source) DO UPDATE SET name = EXCLUDED.name
            RETURNING model_id
            """,
            (
                getattr(metadata, "ModelName", getattr(metadata, "name", None)),
                getattr(metadata, "ModelVersion", getattr(metadata, "version", None)),
                getattr(metadata, "Source", getattr(metadata, "source", None)),
            ),
        )
        model_ids[get_xmi_id(metadata)] = cursor.fetchone()[0]
