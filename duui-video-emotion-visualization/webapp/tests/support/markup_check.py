"""A small reader for the frontend's markup, for the markup tests.

Deliberately stdlib-only (`html.parser`), like contrast_check.py and
cvd_check.py beside it. That is what keeps the accessibility suite
runnable with nothing but pytest — no browser, no database, no
application dependencies — which is in turn what makes it cheap enough
to run on every change. Adding a parser dependency here would cost more
than it saves.

**A helper, not a test.** pytest does not collect this file, and it
asserts nothing on its own. It is driven by `test_markup.py`, which
turns what it reports into the invariants worth holding to.

It does not attempt to be an accessibility engine. It answers structural
questions — which ids exist, what references them, what is focusable and
in what order.

**Where this ends and the linter begins.** `html-validate` owns whether
the markup is *valid*: unclosed tags, bad nesting, attributes that do
not belong on an element. This file owns whether the markup is
*usable*: that a control has a name, that the tab order is sane, that a
reference resolves to something real. A document can be perfectly valid
and unusable, which is why both exist. Neither should grow into the
other — a rule about validity belongs in the linter's configuration, and
a rule about semantics belongs here.
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import overload

INDEX_HTML = Path(__file__).resolve().parents[2] / "src" / "frontend" / "index.html"

# Elements that take focus without an author-supplied tabindex.
NATIVELY_FOCUSABLE = {"button", "input", "select", "textarea", "a"}

# Attributes whose value is one or more ids that must exist.
IDREF_ATTRS = ("aria-controls", "aria-labelledby", "aria-describedby", "for")


class Element:
    """One tag, its attributes, and where it sits in the document."""

    __slots__ = ("tag", "attrs", "order", "text", "parents")

    def __init__(
        self,
        tag: str,
        attrs: dict[str, str],
        order: int,
        parents: tuple["Element", ...],
    ) -> None:
        """Record the tag, its attributes, and its ancestry."""
        self.tag = tag
        self.attrs = attrs
        self.order = order
        self.parents = parents
        self.text = ""

    @overload
    def get(self, name: str) -> str | None: ...

    @overload
    def get(self, name: str, default: str) -> str: ...

    def get(self, name: str, default: str | None = None) -> str | None:
        """Return one attribute's value, or `default`."""
        return self.attrs.get(name, default)

    def has(self, name: str) -> bool:
        """Whether the attribute is present at all."""
        return name in self.attrs

    @property
    def focusable(self) -> bool:
        """Whether this element is in the tab order as written.

        `hidden` and an explicit -1 both take it out; a disabled control
        likewise. Anything CSS does is invisible from here, which is the
        limit of a static read and why the browser sweep in
        a11y_browser_check.js still exists.
        """
        if self.has("hidden") or self.has("disabled"):
            return False
        tabindex = self.get("tabindex")
        if tabindex is not None:
            return tabindex.strip() != "-1"
        if self.tag == "a":
            return self.has("href")
        return self.tag in NATIVELY_FOCUSABLE

    def __repr__(self) -> str:
        """Identify the element by tag and id, for a failure message."""
        ident = f"#{self.get('id')}" if self.has("id") else ""
        return f"<{self.tag}{ident}>"


class _Reader(HTMLParser):
    """Collects every element, in document order, as it parses."""

    def __init__(self) -> None:
        """Start with an empty document and no open tags."""
        super().__init__(convert_charrefs=True)
        self.elements: list[Element] = []
        self._stack: list[Element] = []
        self._order = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Record an opening tag, and push it onto the ancestry."""
        element = Element(
            tag,
            {k: (v if v is not None else "") for k, v in attrs},
            self._order,
            tuple(self._stack),
        )
        self._order += 1
        self.elements.append(element)
        # Void elements never close, so they must not go on the stack.
        if tag not in ("input", "img", "br", "hr", "meta", "link", "source", "track"):
            self._stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        """Record a self-closing tag, which opens and closes at once."""
        element = Element(
            tag,
            {k: (v if v is not None else "") for k, v in attrs},
            self._order,
            tuple(self._stack),
        )
        self._order += 1
        self.elements.append(element)

    def handle_endtag(self, tag: str) -> None:
        """Close the innermost matching tag."""
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        """Accumulate text onto whichever element is open."""
        stripped = data.strip()
        if not stripped:
            return
        for element in self._stack:
            element.text += " " + stripped


class Document:
    """A parsed page, answering structural questions about it."""

    def __init__(self, path: Path = INDEX_HTML) -> None:
        """Read and parse the page at `path`."""
        self.source = path.read_text(encoding="utf-8")
        reader = _Reader()
        reader.feed(self.source)
        self.elements = reader.elements

    def find(self, tag: str | None = None, **attrs: str) -> list[Element]:
        """Return every element matching a tag and attribute values."""
        out = []
        for e in self.elements:
            if tag and e.tag != tag:
                continue
            if all(e.get(k) == v for k, v in attrs.items()):
                out.append(e)
        return out

    def by_id(self, value: str) -> Element | None:
        """Return the element carrying this id, if any."""
        for e in self.elements:
            if e.get("id") == value:
                return e
        return None

    @property
    def ids(self) -> list[str]:
        """Every id in the document, in document order."""
        return [e.get("id", "") for e in self.elements if e.has("id")]

    @property
    def focusable(self) -> list[Element]:
        """Focusable elements in source order.

        That is the tab order, given no positive tabindex anywhere,
        which `test_markup.py` asserts separately.
        """
        return [e for e in self.elements if e.focusable]

    def idrefs(self) -> list[tuple[Element, str, str]]:
        """Every id reference in the page, as element, attribute, id."""
        out = []
        for e in self.elements:
            for attr in IDREF_ATTRS:
                value = e.get(attr)
                if value:
                    for ref in value.split():
                        out.append((e, attr, ref))
        return out

    def accessible_name_source(self, element: Element) -> str | None:
        """
        Where this element's accessible name comes from, or None.

        A deliberately shallow version of the accname algorithm: enough
        to catch a control shipped with no name at all, which is the
        regression worth guarding. `placeholder` is reported separately
        because it is a last-resort fallback rather than a name: it
        disappears the moment someone types, which is precisely when a
        name is still needed.
        """
        if element.get("aria-label", "").strip():
            return "aria-label"
        if element.get("aria-labelledby", "").strip():
            return "aria-labelledby"
        if element.has("id"):
            for label in self.find("label"):
                if label.get("for") == element.get("id"):
                    return "label[for]"
        for parent in element.parents:
            if parent.tag == "label":
                return "wrapping label"
        if element.text.strip():
            return "contents"
        if element.get("title", "").strip():
            return "title"
        if element.get("placeholder", "").strip():
            return "placeholder"
        return None
