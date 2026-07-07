"""
Helpers for iterating CAS content across all sofas/views.

Some DUUI pipelines put annotations from different processing stages
on separate sofas -- for example, video-derived annotations on the
`_InitialView` and transcript/audio-derived annotations on a
`transcriptView` sofa (this is the case for the Bundestag
video-emotion pipeline). `Cas.select()` only walks the single view it
is called on, so enumerating a type end-to-end requires visiting
every view explicitly, which is what `select_across_views` does.
"""

from cassis.typesystem import TypeNotFoundError

_warned_missing_types = set()


def select_across_views(cas, type_name):
    """
    Yield every FeatureStructure of `type_name` across all views/sofas
    in `cas`, de-duplicated by xmi:id.

    If `type_name` isn't defined in the CAS's typesystem at all, this
    prints a one-time warning and yields nothing rather than raising --
    some optional types (e.g. GlobalPerson) may simply not be part of
    a given pipeline's typesystem, and that shouldn't abort the whole
    parse.
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
                    f"[duui_parser] warning: type not found in typesystem, "
                    f"skipping: {type_name}"
                )
            return
