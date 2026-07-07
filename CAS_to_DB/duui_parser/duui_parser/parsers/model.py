"""Parses Model rows.

Two metadata annotation shapes show up across DUUI pipelines and both
feed the same Model table:
  - the generic `model.MetaData` FS
  - `model.HuggingfaceMetaData`, used by transformer-based components
    (it carries the same Name/Version/Source features plus extras
    like HuggingfaceVersion, which the DB schema doesn't have a column
    for and are therefore not persisted).
"""

from ..cas_views import select_across_views
from ..config import TYPES
from ..db import get_or_insert_id
from ..typesystem import get_xmi_id


def _insert_model(cursor, conn, metadata):
    model_id = get_xmi_id(metadata)
    get_or_insert_id(cursor, conn, "Model", "model_id", model_id)
    cursor.execute(
        """
        INSERT INTO Model (model_id, name, version, source)
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


def parse(cas, cursor, conn, context):
    for metadata in select_across_views(cas, TYPES["model_meta_data"]):
        _insert_model(cursor, conn, metadata)
    for metadata in select_across_views(cas, TYPES["huggingface_meta_data"]):
        _insert_model(cursor, conn, metadata)
