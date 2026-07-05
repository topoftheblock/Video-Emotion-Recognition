"""Parses Model rows.

`org.texttechnologylab.annotation.MetaData` (the bare type specified
by the canonical mapping doc) is the common supertype of both the
generic `model.MetaData` FS and `model.HuggingfaceMetaData` (used by
transformer-based components, which carries the same Name/Version/
Source features plus extras like HuggingfaceVersion the DB schema
doesn't have a column for and are therefore not persisted). Since
`cas.select()` includes subtype instances, selecting the bare type
alone already covers every concrete Model row.
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..typesystem import get_xmi_id


def parse(cas, cursor, conn, context):
    for metadata in select_across_views(cas, TYPES["model_meta_data"]):
        model_id = get_xmi_id(metadata)
        cursor.execute(
            """
            INSERT INTO models (model_id, name, version, source)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (model_id) DO NOTHING
            """,
            (
                model_id,
                getattr(metadata, "ModelName", getattr(metadata, "name", None)),
                getattr(metadata, "ModelVersion", getattr(metadata, "version", None)),
                getattr(metadata, "Source", getattr(metadata, "source", None)),
            ),
        )
