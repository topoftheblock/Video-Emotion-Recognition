"""
A tiny reader for the viewer's index.html, for the markup tests.

Deliberately stdlib-only (`html.parser`), like contrast_check.py and
cvd_check.py beside it. That is what keeps the accessibility suite
runnable with nothing but pytest -- no browser, no database, no
application dependencies -- which is in turn what makes it cheap enough
to run on every change. Adding a parser dependency here would cost more
than it saves.

This does not attempt to be an accessibility engine. It answers
structural questions -- which ids exist, what references them, what is
focusable and in what order -- and the tests in test_markup.py turn
those into the handful of invariants Phases 1 and 2 established.
"""

from html.parser import HTMLParser
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parent.parent / "src" / "frontend" / "index.html"

# Elements that take focus without an author-supplied tabindex.
NATIVELY_FOCUSABLE = {"button", "input", "select", "textarea", "a"}

# Attributes whose value is one or more ids that must exist.
IDREF_ATTRS = ("aria-controls", "aria-labelledby", "aria-describedby", "for")


class Element:
    __slots__ = ("tag", "attrs", "order", "text", "parents")

    def __init__(self, tag, attrs, order, parents):
        self.tag = tag
        self.attrs = attrs
        self.order = order
        self.parents = parents
        self.text = ""

    def get(self, name, default=None):
        return self.attrs.get(name, default)

    def has(self, name):
        return name in self.attrs

    @property
    def focusable(self):
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

    def __repr__(self):
        ident = f"#{self.get('id')}" if self.has("id") else ""
        return f"<{self.tag}{ident}>"


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self._stack = []
        self._order = 0

    def handle_starttag(self, tag, attrs):
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

    def handle_startendtag(self, tag, attrs):
        element = Element(
            tag,
            {k: (v if v is not None else "") for k, v in attrs},
            self._order,
            tuple(self._stack),
        )
        self._order += 1
        self.elements.append(element)

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        stripped = data.strip()
        if not stripped:
            return
        for element in self._stack:
            element.text += " " + stripped


class Document:
    def __init__(self, path=INDEX_HTML):
        self.source = path.read_text(encoding="utf-8")
        reader = _Reader()
        reader.feed(self.source)
        self.elements = reader.elements

    def find(self, tag=None, **attrs):
        out = []
        for e in self.elements:
            if tag and e.tag != tag:
                continue
            if all(e.get(k) == v for k, v in attrs.items()):
                out.append(e)
        return out

    def by_id(self, value):
        for e in self.elements:
            if e.get("id") == value:
                return e
        return None

    @property
    def ids(self):
        return [e.get("id") for e in self.elements if e.has("id")]

    @property
    def focusable(self):
        """Focusable elements in source order -- the tab order, given no
        positive tabindex anywhere (which test_markup.py asserts)."""
        return [e for e in self.elements if e.focusable]

    def idrefs(self):
        """[(element, attribute, id)] for every id-reference in the file."""
        out = []
        for e in self.elements:
            for attr in IDREF_ATTRS:
                value = e.get(attr)
                if value:
                    for ref in value.split():
                        out.append((e, attr, ref))
        return out

    def accessible_name_source(self, element):
        """
        Where this element's accessible name comes from, or None.

        A deliberately shallow version of the accname algorithm: enough
        to catch a control shipped with no name at all, which is the
        regression worth guarding. `placeholder` is reported separately
        because it is a last-resort fallback rather than a name -- it
        disappears the moment someone types, which is exactly the
        finding Phase 1.2 fixed.
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
