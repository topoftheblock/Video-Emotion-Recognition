"""
Typesystem loading/patching and small CAS FeatureStructure helpers.

Isolating the XML patching here means the "hacks" needed to make a
Java-authored typesystem loadable in Python (cassis) stay in exactly
one place, instead of being buried in the middle of a `__main__` block.
"""

import io

from cassis import load_typesystem, merge_typesystems

from .config import INJECTED_BASE_TYPES_XML, SUPERTYPE_PATCHES, TYPESYSTEM_FILES


def get_xmi_id(feature_struct):
    """Safely extract the XMI ID from a cassis FeatureStructure."""
    if feature_struct is None:
        return None
    if hasattr(feature_struct, "xmiID"):
        return feature_struct.xmiID
    return None


def as_list(value):
    """
    Normalize a multi-valued feature into a plain Python list,
    regardless of which shape cassis handed back: a plain list
    already, an FSArray-typed FeatureStructure wrapper (real vector
    lives under `.elements`), a single bare FeatureStructure/value, or
    None.

    This matters because iterating an FSArray wrapper directly (e.g.
    `for x in fs.scores`) doesn't raise -- it silently falls through
    to FeatureStructure's dict-style `__getitem__`, which then raises
    a confusing AttributeError deep inside cassis. Always going
    through `as_list` avoids that trap.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if hasattr(value, "elements"):
        return list(value.elements)
    return [value]


def patch_and_load_ts(filepath, inject_base_types=False):
    """
    Read a typesystem XML file and patch it in memory so cassis can
    load it in Python:

    1. Swap out missing external Java supertypes for a standard
       UIMA annotation supertype.
    2. Optionally inject base type descriptions (Video/document
       metadata) that would otherwise be lost entirely.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        xml_content = f.read()

    for old_supertype, new_supertype in SUPERTYPE_PATCHES.items():
        xml_content = xml_content.replace(
            f"<supertypeName>{old_supertype}</supertypeName>",
            f"<supertypeName>{new_supertype}</supertypeName>",
        )

    if inject_base_types:
        xml_content = xml_content.replace(
            "</types>", INJECTED_BASE_TYPES_XML + "\n</types>"
        )

    return load_typesystem(io.BytesIO(xml_content.encode("utf-8")))


def load_merged_typesystem():
    """
    Load all configured typesystem files, patching each, and merge
    them into a single typesystem. Base types are injected into only
    the first file to avoid duplicate-type errors on merge.
    """
    filepaths = list(TYPESYSTEM_FILES.values())
    if not filepaths:
        raise ValueError("No typesystem files configured in TYPESYSTEM_FILES.")

    loaded = [
        patch_and_load_ts(path, inject_base_types=(i == 0))
        for i, path in enumerate(filepaths)
    ]
    return merge_typesystems(loaded)
