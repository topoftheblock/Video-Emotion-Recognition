"""Structural accessibility invariants for the page's markup.

See docs/accessibility.md. Every one of these corresponds to something
that was actually wrong once — an unlabeled
slider, a page with no `h1`, an `aria-expanded` on an element that could
not carry it, an explanation reachable only by hovering. The point is
that none of those can come back silently.

What this cannot see: anything CSS does, anything JavaScript renders,
and what a screen reader actually announces. The person rows and Ask
results are built at runtime and are covered by
tests/a11y_browser_check.js instead; the announcement layer is covered
by nothing automated and never will be (see "Known gaps" in the guide).
"""

from collections import Counter

import pytest
from support.markup_check import Document, Element

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


@pytest.fixture(scope="module")
def doc() -> Document:
    """The parsed page, read once for the whole module."""
    return Document()


# --- Document structure -------------------------------------------------


def test_html_declares_a_language(doc: Document) -> None:
    """A page with no language is read aloud in the wrong one."""
    html = doc.find("html")
    assert html, "no <html> element"
    assert html[0].get("lang", "").strip(), "<html> needs a lang attribute"


def test_exactly_one_h1(doc: Document) -> None:
    """One top-level heading: the document's actual title."""
    h1s = doc.find("h1")
    assert len(h1s) == 1, f"expected one <h1>, found {len(h1s)}"


def test_heading_levels_do_not_skip(doc: Document) -> None:
    """Heading navigation walks the levels, so none may be missing.

    A jump straight from one level to two below it leaves a heading
    with no parent.
    """
    levels = [int(e.tag[1]) for e in doc.elements if e.tag in HEADING_TAGS]
    assert levels, "no headings at all"
    assert levels[0] == 1, f"first heading is h{levels[0]}, not h1"
    for previous, current in zip(levels, levels[1:]):
        assert current <= previous + 1, f"h{previous} is followed by h{current}"


def test_ids_are_unique(doc: Document) -> None:
    """A repeated id makes every reference to it ambiguous, and the
    browser silently resolves to the first one."""
    counts = Counter(doc.ids)
    duplicates = sorted(name for name, n in counts.items() if n > 1)
    assert not duplicates, f"duplicate ids: {duplicates}"


def test_every_id_reference_resolves(doc: Document) -> None:
    """`aria-controls`, `aria-labelledby`, `aria-describedby` and `for`
    pointing at nothing is worse than not being there: it silently
    removes the relationship rather than failing loudly."""
    broken = [
        f'{element!r} {attr}="{ref}"'
        for element, attr, ref in doc.idrefs()
        if doc.by_id(ref) is None
    ]
    assert not broken, "id references pointing at nothing:\n  " + "\n  ".join(broken)


# --- The tab order ------------------------------------------------------


def test_no_positive_tabindex(doc: Document) -> None:
    """A positive tabindex pulls an element out of document order and
    forces every other control on the page to be reasoned about
    relative to it. It is also what makes the source-order tab sweep in
    markup_check.py a valid stand-in for the real thing."""
    offenders = []
    for element in doc.elements:
        raw = element.get("tabindex")
        if raw is None:
            continue
        try:
            if int(raw.strip()) > 0:
                offenders.append(element)
        except ValueError:
            offenders.append(element)  # not a number at all
    assert not offenders, f"positive or malformed tabindex on {offenders}"


def test_skip_link_is_the_first_focusable_element(doc: Document) -> None:
    """Anything before the skip link is something it cannot skip."""
    first = doc.focusable[0]
    assert "skip-link" in first.get("class", ""), (
        f"first focusable element is {first!r}, not the skip link — "
        "anything before it is something a keyboard user cannot skip"
    )


def test_skip_link_targets_a_real_and_focusable_element(doc: Document) -> None:
    """A skip link landing nowhere focusable just moves the scroll."""
    link = doc.find("a", **{"class": "skip-link"})[0]
    href = link.get("href", "")
    assert href.startswith("#"), f"skip link href is {href!r}"
    target = doc.by_id(href[1:])
    assert target is not None, f"skip link points at {href}, which does not exist"
    assert target.get("tabindex") == "-1", (
        f'{target!r} needs tabindex="-1" or the skip link moves the scroll '
        "position without moving focus"
    )


def test_every_focusable_element_is_inside_a_landmark(doc: Document) -> None:
    """
    Content outside every landmark is skipped by landmark navigation.

    An unnamed <section> is *not* a landmark, which is what left the
    whole Ask panel orphaned until it was given an aria-labelledby. The
    skip link is the one legitimate exception: it belongs before
    everything, including the landmarks.
    """

    def is_landmark(element: Element) -> bool:
        """Whether this is a landmark a screen reader announces."""
        if element.tag in ("header", "main", "nav", "aside", "footer"):
            return True
        if element.tag in ("section", "form"):
            return bool(element.get("aria-label") or element.get("aria-labelledby"))
        return False

    orphans = [
        e
        for e in doc.focusable
        if "skip-link" not in e.get("class", "")
        and not any(is_landmark(p) for p in e.parents)
    ]
    assert not orphans, f"focusable elements outside every landmark: {orphans}"


# --- Names --------------------------------------------------------------


def test_every_focusable_element_has_an_accessible_name(doc: Document) -> None:
    """A control with no name is announced as its tag, and no more."""
    unnamed = [e for e in doc.focusable if doc.accessible_name_source(e) is None]
    assert not unnamed, f"focusable elements with no accessible name: {unnamed}"


def test_no_control_is_named_only_by_its_placeholder(doc: Document) -> None:
    """A placeholder is a fallback, not a name.

    It vanishes on the first keystroke, which is exactly when the name
    is still needed.
    """
    offenders = [
        e for e in doc.focusable if doc.accessible_name_source(e) == "placeholder"
    ]
    assert not offenders, f"named only by placeholder: {offenders}"


def test_no_control_is_named_only_by_its_title(doc: Document) -> None:
    """A title is unreachable by keyboard and invisible on touch.

    It is fine *alongside* a name, never as the only one.
    """
    offenders = [e for e in doc.focusable if doc.accessible_name_source(e) == "title"]
    assert not offenders, f"named only by title: {offenders}"


def test_the_range_input_is_named_and_not_left_to_its_raw_value(
    doc: Document,
) -> None:
    """A slider announced as a bare number says nothing useful."""
    scrub = doc.by_id("scrub")
    assert scrub is not None and scrub.get("type") == "range"
    assert scrub.get("aria-label", "").strip(), "#scrub needs an aria-label"


# --- Widget wiring ------------------------------------------------------


def test_combobox_state_lives_on_the_element_that_has_the_role(doc: Document) -> None:
    """
    aria-expanded belongs to whatever carries role="combobox".

    It used to sit on the wrapper <div>, which may not carry it at all —
    invalid markup that also left the input permanently reading
    "collapsed". A plain div with aria-expanded is the signature of that
    bug returning.
    """
    combobox = [e for e in doc.elements if e.get("role") == "combobox"]
    assert len(combobox) == 1, f"expected one role=combobox, found {len(combobox)}"
    assert combobox[0].has("aria-expanded"), "the combobox input needs aria-expanded"

    stray = [
        e
        for e in doc.elements
        if e.has("aria-expanded")
        and not e.get("role")
        and e.tag not in ("button", "summary")
    ]
    assert not stray, f"aria-expanded on elements that cannot carry it: {stray}"


def test_disclosure_buttons_are_wired_both_ways(doc: Document) -> None:
    """Each legend toggle must be a real button, declare its state, and
    point at the paragraph it opens."""
    toggles = [e for e in doc.elements if "person-legend-toggle" in e.get("class", "")]
    assert toggles, "no legend disclosure toggles found"
    for toggle in toggles:
        assert toggle.tag == "button", f"{toggle!r} should be a <button>"
        assert toggle.get("type") == "button", f'{toggle!r} needs type="button"'
        assert toggle.has("aria-expanded"), f"{toggle!r} needs aria-expanded"
        target = doc.by_id(toggle.get("aria-controls", ""))
        assert target is not None, f"{toggle!r} aria-controls points at nothing"
        assert target.has("hidden"), (
            f"{target!r} should start hidden so aria-expanded=false is true on load"
        )


def test_toggle_buttons_declare_their_pressed_state(doc: Document) -> None:
    """The CC toggle is a two-state control; without aria-pressed it
    announces as a plain button and its state is invisible."""
    cc = doc.by_id("subtitleToggle")
    assert cc is not None
    assert cc.get("aria-pressed") in ("true", "false"), (
        "#subtitleToggle needs aria-pressed"
    )
