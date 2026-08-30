"""Loading and patching typesystems, plus feature-structure helpers.

Isolating the XML patching here keeps the work needed to make a
Java-authored typesystem loadable under cassis in exactly one place.
What that work is, and why each part of it is necessary, is documented
on `load_merged_typesystem`.
"""

import io
import re
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

from cassis import load_typesystem
from cassis.typesystem import FeatureStructure, TypeSystem

try:
    # Private API: the UIMA built-in type names cassis already knows
    # without a typeDescription for them. Used below to avoid
    # auto-stubbing something that is already a real builtin.
    from cassis.typesystem import _PREDEFINED_TYPES as KNOWN_BUILTIN_TYPES
except ImportError:
    # If a future cassis renames or removes this, keep the auto-stub
    # scan working — slightly more conservatively — rather than failing
    # on import.
    KNOWN_BUILTIN_TYPES = {
        "uima.cas.TOP",
        "uima.tcas.Annotation",
        "uima.cas.AnnotationBase",
        "uima.cas.String",
        "uima.cas.Integer",
        "uima.cas.Double",
        "uima.cas.Float",
        "uima.cas.Boolean",
        "uima.cas.Byte",
        "uima.cas.Short",
        "uima.cas.Long",
        "uima.cas.FSArray",
        "uima.cas.StringArray",
        "uima.cas.IntegerArray",
        "uima.cas.DoubleArray",
        "uima.cas.FloatArray",
        "uima.cas.BooleanArray",
        "uima.cas.ByteArray",
        "uima.cas.ShortArray",
        "uima.cas.LongArray",
        "uima.cas.ArrayBase",
        "uima.cas.FSList",
        "uima.cas.StringList",
        "uima.cas.IntegerList",
        "uima.cas.FloatList",
        "uima.cas.ListBase",
        "uima.cas.EmptyFSList",
        "uima.cas.EmptyStringList",
        "uima.cas.EmptyIntegerList",
        "uima.cas.EmptyFloatList",
        "uima.cas.NonEmptyFSList",
        "uima.cas.NonEmptyStringList",
        "uima.cas.NonEmptyIntegerList",
        "uima.cas.NonEmptyFloatList",
        "uima.cas.Sofa",
        "uima.cas.NULL",
    }

from ..config import TYPESYSTEM_FILES
from .types import IGNORED_ABSENT_TYPES, INJECTED_FALLBACK_TYPES

# How cassis phrases the warning it raises when the document references
# a type the typesystem does not define. Matched literally, per type
# name, so nothing else is swallowed by accident.
_ABSENT_TYPE_WARNING = "Type with name [{name}] not found!"


@contextmanager
def loading_cas_quietly(
    type_names: Iterable[str] = IGNORED_ABSENT_TYPES,
) -> Iterator[None]:
    """Silence the "type not found" warning for exactly these types.

    A real CAS carries whole annotation layers this importer has no use
    for — see `IGNORED_ABSENT_TYPES`. cassis is right to warn, since it
    is dropping annotations, but for those layers dropping them is the
    intent, and a dozen expected warnings per file hide the one that
    would matter. Filtering by exact message keeps every other
    UserWarning, from cassis or anywhere else, visible.

    Args:
        type_names: The type names whose absence is expected.

    Yields:
        Nothing; the filter is active for the duration of the block.
    """
    with warnings.catch_warnings():
        for name in type_names:
            warnings.filterwarnings(
                "ignore",
                message=re.escape(_ABSENT_TYPE_WARNING.format(name=name)),
                category=UserWarning,
            )
        yield


def get_xmi_id(feature_struct: FeatureStructure | None) -> int | None:
    """Return a feature structure's `xmi:id`, or None if it has none."""
    if feature_struct is None:
        return None
    if hasattr(feature_struct, "xmiID"):
        return feature_struct.xmiID
    return None


def as_list(value: Any) -> list[Any]:
    """Normalize a multi-valued feature into a plain list.

    cassis hands these back in four shapes: a list already, an FSArray
    wrapper whose real contents sit under `.elements`, a single bare
    value, or None.

    This matters because iterating an FSArray wrapper directly does not
    raise. It silently falls through to the dict-style `__getitem__`,
    which then raises a confusing AttributeError from deep inside
    cassis. Going through `as_list` avoids that trap.

    Args:
        value: The feature value, in whichever shape cassis returned.

    Returns:
        The values as a list; empty when there are none.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if hasattr(value, "elements"):
        return list(value.elements)
    return [value]


def _local_tag(elem: ET.Element) -> str:
    """Return a tag name with its namespace prefix removed."""
    return elem.tag.rsplit("}", 1)[-1]


def _direct_child(elem: ET.Element, local_name: str) -> ET.Element | None:
    """Return the first direct child with this tag name, or None."""
    for child in elem:
        if _local_tag(child) == local_name:
            return child
    return None


def _direct_child_text(elem: ET.Element, local_name: str) -> str | None:
    """Return that child's stripped text, or None if it has none."""
    child = _direct_child(elem, local_name)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _strip_namespace(elem: ET.Element) -> ET.Element:
    """Strip namespace prefixes from an element and its descendants.

    Re-serializing an element that kept its prefix would carry a
    namespace declaration differing from sibling elements pulled out of
    a different source file, so they could not be mixed.
    """
    elem.tag = _local_tag(elem)
    for child in elem:
        _strip_namespace(child)
    return elem


def _load_type_descriptions(filepath: str) -> list[ET.Element]:
    """Parse one typesystem file into its typeDescription elements.

    Args:
        filepath: Path to a UIMA typeSystemDescription XML file.

    Returns:
        The typeDescriptions in document order, namespace-stripped so
        they mix freely with those from other files.

    Raises:
        ValueError: If the file has no `<types>` element.
    """
    tree = ET.parse(filepath)
    root = tree.getroot()
    types_elem = _direct_child(root, "types")
    if types_elem is None:
        raise ValueError(
            f"Could not find a <types> element in {filepath!r} — "
            "is this a valid UIMA typeSystemDescription XML file?"
        )
    return [
        _strip_namespace(td) for td in types_elem if _local_tag(td) == "typeDescription"
    ]


def _collect_type_descriptions() -> list[ET.Element]:
    """Merge every configured typesystem file into one ordered list.

    The configured files overlap heavily rather than being
    complementary fragments: IdentityEmotionTypeSystem.xml carries its
    own copies of nearly every type that MultimodalIdentityTypeSystem
    and EmotionTypeSystem also define. Concatenating them verbatim
    raises a duplicate-type error the moment the genuinely missing
    types are supplied, so they are de-duplicated by name here.

    First occurrence wins, and `TYPESYSTEM_FILES` lists the files in a
    stable order, so the result is deterministic.

    Returns:
        The merged typeDescriptions, de-duplicated by type name.

    Raises:
        ValueError: If no typesystem files are configured.
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


def _find_undefined_referenced_types(
    type_descriptions: list[ET.Element],
) -> set[str]:
    """Find every referenced type that nothing here defines.

    Scans each typeDescription's supertype, feature range and element
    types, and returns those that are neither a UIMA builtin nor
    defined by a typeDescription in the list.

    This generalizes what would otherwise be an endless one-off patch
    per missing type: rather than waiting for the next failure from
    cassis and hard-coding another fallback, every gap is caught in one
    pass.

    Args:
        type_descriptions: The merged typeDescriptions.

    Returns:
        The undefined type names.
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


def _stub_type_xml(type_name: str) -> ET.Element:
    """Build a featureless typeDescription for an undefined type.

    Enough for cassis to resolve the reference. Instances of such a
    type, should any appear in a CAS, carry nothing readable beyond
    `begin`, `end` and `sofa`, since its real fields are unknown.

    Args:
        type_name: The fully qualified name to define.

    Returns:
        A typeDescription element deriving from `uima.tcas.Annotation`.
    """
    description = (
        "Auto-stubbed: referenced by another type's feature but never "
        "defined in the provided typesystem files."
    )
    return ET.fromstring(
        f"<typeDescription>"
        f"<name>{type_name}</name>"
        f"<description>{description}</description>"
        f"<supertypeName>uima.tcas.Annotation</supertypeName>"
        f"</typeDescription>"
    )


def load_merged_typesystem() -> TypeSystem:
    """Load every configured typesystem file as one merged typesystem.

    The merge happens *before* cassis resolves any type reference,
    which is what makes it work. Three problems are handled, all
    confirmed against the real typesystem files and CAS:

    1. **Cross-file forward references** — a feature in one file whose
       elementType is defined only in a sibling file. `load_typesystem`
       resolves every reference the moment it parses a document, so
       loading each file independently fails the instant it meets one.
       Fixed by combining every file's typeDescriptions into a single
       document before parsing.

    2. **Duplicate definitions across files.** The files overlap
       heavily rather than being complementary fragments; see
       `_collect_type_descriptions`. Fixed by de-duplicating on type
       name, first occurrence winning.

    3. **Types referenced but never defined in any file** — as a
       supertype or a feature range. `MultimediaElement`, `AudioToken`,
       the bare `MetaData` and `Embedding` all come from shared
       typesystem imports that were not included. Fixed in two layers:
       `INJECTED_FALLBACK_TYPES` supplies a hand-confirmed field shape
       for the types this importer actually reads, and anything else
       still missing gets a featureless stub, so cassis can resolve the
       typesystem as a whole instead of refusing to start.

    Returns:
        The merged, loadable typesystem.
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
            f"[importer] warning: {type_name!r} is referenced by a feature "
            "but not defined in any provided typesystem file — auto-stubbing "
            "it as a featureless type so loading can proceed."
        )
        type_descriptions.append(_stub_type_xml(type_name))

    root = ET.Element("typeSystemDescription")
    types_elem = ET.SubElement(root, "types")
    for type_desc in type_descriptions:
        types_elem.append(type_desc)

    combined_xml = ET.tostring(root, encoding="unicode")
    return load_typesystem(io.BytesIO(combined_xml.encode("utf-8")))
