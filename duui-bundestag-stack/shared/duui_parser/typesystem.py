"""
Typesystem loading/patching and small CAS FeatureStructure helpers.

Isolating the XML patching here means the "hacks" needed to make a
Java-authored typesystem loadable in Python (cassis) stay in exactly
one place, instead of being buried in the middle of a `__main__` block.
"""

import io
import re
import warnings
import xml.etree.ElementTree as ET
from contextlib import contextmanager

from cassis import load_typesystem

try:
    # Private API: the set of UIMA built-in type names cassis already
    # knows about without any typeDescription for them. Used below to
    # avoid auto-stubbing something that's already a real builtin.
    from cassis.typesystem import _PREDEFINED_TYPES as KNOWN_BUILTIN_TYPES
except ImportError:
    # Fallback if a future cassis version renames/removes this -- keep
    # the auto-stub scan working (just slightly more conservative)
    # rather than crashing on import.
    KNOWN_BUILTIN_TYPES = {
        "uima.cas.TOP", "uima.tcas.Annotation", "uima.cas.AnnotationBase",
        "uima.cas.String", "uima.cas.Integer", "uima.cas.Double", "uima.cas.Float",
        "uima.cas.Boolean", "uima.cas.Byte", "uima.cas.Short", "uima.cas.Long",
        "uima.cas.FSArray", "uima.cas.StringArray", "uima.cas.IntegerArray",
        "uima.cas.DoubleArray", "uima.cas.FloatArray", "uima.cas.BooleanArray",
        "uima.cas.ByteArray", "uima.cas.ShortArray", "uima.cas.LongArray",
        "uima.cas.ArrayBase", "uima.cas.FSList", "uima.cas.StringList",
        "uima.cas.IntegerList", "uima.cas.FloatList", "uima.cas.ListBase",
        "uima.cas.EmptyFSList", "uima.cas.EmptyStringList", "uima.cas.EmptyIntegerList",
        "uima.cas.EmptyFloatList", "uima.cas.NonEmptyFSList", "uima.cas.NonEmptyStringList",
        "uima.cas.NonEmptyIntegerList", "uima.cas.NonEmptyFloatList",
        "uima.cas.Sofa", "uima.cas.NULL",
    }

from .config import (
    IGNORED_ABSENT_TYPES,
    INJECTED_FALLBACK_TYPES,
    TYPESYSTEM_FILES,
)

# How cassis phrases the warning it raises (cassis/xmi.py) when the XMI
# references a type the typesystem doesn't define. Matched literally,
# per type name, so nothing else gets swallowed by accident.
_ABSENT_TYPE_WARNING = "Type with name [{name}] not found!"


@contextmanager
def loading_cas_quietly(type_names=IGNORED_ABSENT_TYPES):
    """
    Silence cassis's "Type with name [X] not found!" warning for exactly
    the types in `type_names`, and nothing else.

    A real CAS carries whole annotation layers this importer has no use
    for (see IGNORED_ABSENT_TYPES). cassis is right to warn -- it is
    dropping annotations -- but for those layers dropping them is the
    intent, and a dozen expected warnings per file hide the one that
    would actually matter. Filtering by exact message keeps every other
    UserWarning, from cassis or anywhere else, visible.
    """
    with warnings.catch_warnings():
        for name in type_names:
            warnings.filterwarnings(
                "ignore",
                message=re.escape(_ABSENT_TYPE_WARNING.format(name=name)),
                category=UserWarning,
            )
        yield


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


def _local_tag(elem):
    """Strip any {namespace} prefix ElementTree adds to a tag name."""
    return elem.tag.rsplit("}", 1)[-1]


def _direct_child(elem, local_name):
    for child in elem:
        if _local_tag(child) == local_name:
            return child
    return None


def _direct_child_text(elem, local_name):
    child = _direct_child(elem, local_name)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _strip_namespace(elem):
    """Recursively strip {namespace} prefixes from an element and its
    descendants, so re-serializing it later doesn't carry a
    namespace declaration that differs from sibling elements pulled
    from a different source file."""
    elem.tag = _local_tag(elem)
    for child in elem:
        _strip_namespace(child)
    return elem


def _load_type_descriptions(filepath):
    """
    Parse one typesystem XML file and return its <typeDescription>
    elements as a list, in document order, namespace-stripped so they
    can be freely mixed with typeDescriptions from other files.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()
    types_elem = _direct_child(root, "types")
    if types_elem is None:
        raise ValueError(
            f"Could not find a <types> element in {filepath!r} -- "
            "is this a valid UIMA typeSystemDescription XML file?"
        )
    return [_strip_namespace(td) for td in types_elem if _local_tag(td) == "typeDescription"]


def _collect_type_descriptions():
    """
    Load every configured typesystem file and merge their
    typeDescriptions into one de-duplicated, ordered list.

    These typesystem files turned out to be heavily overlapping, not
    complementary fragments: confirmed against the real files that
    IdentityEmotionTypeSystem.xml already contains its own copies of
    every type also defined in MultimodalIdentityTypeSystem.xml (and
    EmotionTypeSystem.xml) -- 12 of the ~13 types across the three
    files are exact duplicates. Concatenating them verbatim raises a
    "duplicate type" error the moment the genuinely-missing types
    (below) are fixed, so types are de-duplicated by name here,
    keeping the first occurrence (files are listed in
    TYPESYSTEM_FILES/config in a stable order, so this is
    deterministic).
    """
    filepaths = list(TYPESYSTEM_FILES.values())
    if not filepaths:
        raise ValueError("No typesystem files configured in TYPESYSTEM_FILES.")

    seen_names = set()
    ordered_type_descriptions = []
    for path in filepaths:
        for type_desc in _load_type_descriptions(path):
            name = _direct_child_text(type_desc, "name")
            if name and name in seen_names:
                continue
            if name:
                seen_names.add(name)
            ordered_type_descriptions.append(type_desc)

    return ordered_type_descriptions


def _find_undefined_referenced_types(type_descriptions):
    """
    Scan every typeDescription's supertype/feature range/element types
    and return whichever of those are neither a UIMA builtin nor
    defined by any typeDescription in the given list.

    This generalizes what would otherwise be an endless one-off patch
    per missing type: rather than waiting for the next KeyError from
    cassis and hardcoding another fallback, every gap like this gets
    caught in one pass.
    """
    defined_types = {
        _direct_child_text(td, "name")
        for td in type_descriptions
        if _direct_child_text(td, "name")
    }

    referenced_types = set()
    for type_desc in type_descriptions:
        supertype = _direct_child_text(type_desc, "supertypeName")
        if supertype:
            referenced_types.add(supertype)
        for feature in type_desc.iter("featureDescription"):
            for tag in ("rangeTypeName", "elementType"):
                text = _direct_child_text(feature, tag)
                if text:
                    referenced_types.add(text)

    return referenced_types - defined_types - KNOWN_BUILTIN_TYPES


def _stub_type_xml(type_name):
    """A minimal, featureless typeDescription for a type that's
    referenced somewhere but never actually defined -- enough for
    cassis to resolve the reference. Any real value on instances of
    this type (if any ever appear in a CAS) beyond `begin`/`end`/`sofa`
    won't be readable, since we don't know its real fields."""
    return ET.fromstring(f"""
<typeDescription>
    <name>{type_name}</name>
    <description>Auto-stubbed: referenced by another type's feature but never defined in the provided typesystem files.</description>
    <supertypeName>uima.tcas.Annotation</supertypeName>
</typeDescription>
""")


def load_merged_typesystem():
    """
    Load all configured typesystem files and merge them into a single
    typesystem *before* cassis resolves any type references.

    Three problems are handled here, all confirmed against the real
    Bundestag video-emotion typesystem files and CAS:

    1. Cross-file forward references -- e.g. a feature in one file
       whose elementType is a type defined only in a sibling file.
       cassis's `load_typesystem` resolves every type reference the
       moment it parses a document, so loading each file independently
       (the original approach, via `merge_typesystems`) fails the
       instant it hits such a reference. Fixed by combining every
       file's typeDescriptions into one document before parsing.

    2. Duplicate type definitions across files -- the three files
       turned out to overlap heavily rather than being complementary
       fragments (see `_collect_type_descriptions`). Fixed by
       de-duplicating by type name, first occurrence wins.

    3. Types referenced (as a supertype or feature range) but never
       defined in *any* of the three files -- confirmed to be
       `MultimediaElement`, `AudioToken`, the bare `MetaData`, and
       `Embedding`, all evidently coming from external/shared
       typesystem imports (`<imports>` by name, e.g.
       `desc.type.TextTechnologyMultimedia`) that weren't included.
       Fixed with two layers: INJECTED_FALLBACK_TYPES supplies a real,
       hand-confirmed field shape for the specific types this parser
       reads; anything else still missing gets a generic featureless
       stub so cassis can resolve the type system as a whole instead
       of refusing to start.
    """
    type_descriptions = _collect_type_descriptions()
    defined_names = {_direct_child_text(td, "name") for td in type_descriptions}

    for type_name, fallback_xml in INJECTED_FALLBACK_TYPES.items():
        if type_name not in defined_names:
            type_descriptions.append(ET.fromstring(fallback_xml))
            defined_names.add(type_name)

    still_missing = _find_undefined_referenced_types(type_descriptions)
    for type_name in sorted(still_missing):
        print(
            f"[duui_parser] warning: {type_name!r} is referenced by a feature "
            "but not defined in any provided typesystem file -- auto-stubbing "
            "it as a featureless type so loading can proceed."
        )
        type_descriptions.append(_stub_type_xml(type_name))

    root = ET.Element("typeSystemDescription")
    types_elem = ET.SubElement(root, "types")
    for type_desc in type_descriptions:
        types_elem.append(type_desc)

    combined_xml = ET.tostring(root, encoding="unicode")
    return load_typesystem(io.BytesIO(combined_xml.encode("utf-8")))
