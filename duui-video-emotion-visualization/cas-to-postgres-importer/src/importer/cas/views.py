"""Iterating CAS content across every sofa.

Some DUUI pipelines put annotations from different processing stages on
separate sofas — video-derived annotations on `_InitialView` and
transcript or audio-derived ones on a `transcriptView` sofa, say.
`Cas.select()` only walks the single view it is called on, so
enumerating a type end to end means visiting every view explicitly.
That is what `select_across_views` does.
"""

from collections.abc import Iterator

from cassis import Cas
from cassis.typesystem import FeatureStructure, TypeNotFoundError

_warned_missing_types: set[str] = set()


def select_across_views(cas: Cas, type_name: str) -> Iterator[FeatureStructure]:
    """Yield every feature structure of `type_name`, across all views.

    De-duplicated by `xmi:id`, since a structure reachable from two
    views would otherwise be yielded twice.

    A type the CAS's typesystem does not define at all produces a
    one-time warning and no results, rather than an exception: a
    pipeline that does not run every annotator — no diarization, no
    shot detection — legitimately produces a typesystem without those
    types, and a missing optional layer should not abort the parse.

    The warning is meant to stay rare enough to be worth reading. A type
    this importer selects on every run but no typesystem ever defines is
    noise, and belongs in `types.IGNORED_ABSENT_TYPES`, or nowhere.

    Args:
        cas: The loaded CAS to search.
        type_name: Fully qualified UIMA type name.

    Yields:
        Each matching feature structure, including subtype instances.
    """
    seen_ids = set()
    for view in cas.views:
        view_cas = cas.get_view(view.sofa.sofaID)
        try:
            for fs in view_cas.select(type_name):
                fs_id = getattr(fs, "xmiID", None)
                key = fs_id if fs_id is not None else id(fs)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                yield fs
        except TypeNotFoundError:
            if type_name not in _warned_missing_types:
                _warned_missing_types.add(type_name)
                print(
                    f"[importer] warning: type not found in typesystem, "
                    f"skipping: {type_name}"
                )
            return


def select_exact_type(cas: Cas, type_name: str) -> Iterator[FeatureStructure]:
    """Like `select_across_views`, but excluding subtype instances.

    `cas.select()`, and so `select_across_views`, returns instances of
    the given type *and of all its subtypes*. That is usually what you
    want — except for a type like `MultimediaElement`, which in the real
    Bundestag typesystem is the common supertype of most time-bounded
    annotations in the pipeline: Shot, Detection, SpeakerSegment,
    SpeakerSentence, Emotion, and more.

    Selecting it naively to find the one top-level MultimediaElement
    record, as `parsers/video.py` needs to, would instead return every
    Shot, Detection and Emotion in the CAS, and silently take whichever
    came first.

    Args:
        cas: The loaded CAS to search.
        type_name: Fully qualified UIMA type name.

    Yields:
        Only structures whose own concrete type is exactly `type_name`.
    """
    for fs in select_across_views(cas, type_name):
        if fs.type.name == type_name:
            yield fs
