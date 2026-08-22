"""Parses Model rows.

`org.texttechnologylab.annotation.MetaData` (the bare type specified
by the canonical mapping doc) is the common supertype of both the
generic `model.MetaData` FS and `model.HuggingfaceMetaData` (used by
transformer-based components, which carries the same Name/Version/
Source features plus extras like HuggingfaceVersion the DB schema
doesn't have a column for and are therefore not persisted). Since
`cas.select()` includes subtype instances, selecting the bare type
alone already covers every concrete Model row.

`models` is the one table not keyed by (video_id, xmi:id): a model is
corpus-global -- the same face model processes every video -- so it is
keyed by what actually identifies it, (name, version, source), and the
row is shared across videos instead of being duplicated per import.
The database therefore assigns `model_id`, and this step records
xmi:id -> model_id in `context` so parsers/embedding.py can translate
the model references its annotations carry.
"""

from ..cas.views import select_across_views
from ..cas.types import TYPES
from ..cas.typesystem import get_xmi_id


def parse(cas, cursor, context):
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
