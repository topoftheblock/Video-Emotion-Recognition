"""
Stylesheet invariants for the viewer's frontend.

These guard Phases 4 and 5 of docs/accessibility.md -- the type scale
and the adaptive rendering modes -- and one thing neither phase covers:
that every custom property a stylesheet reads is actually defined
somewhere. An undefined `var(--typo)` does not error; it resolves to
nothing, and the declaration is dropped. That failure is silent, which
is precisely why it is worth a test.

Regex over the stylesheets rather than a CSS parser, for the same
reason markup_check.py uses html.parser: keeping the accessibility suite
free of third-party dependencies is what keeps it cheap to run. The
stylesheets here are hand-written and regular enough for that to hold;
if they ever stop being, this is the file that should grow a parser.
"""

import re
from pathlib import Path

import pytest

CSS_DIR = Path(__file__).resolve().parent.parent / "src" / "frontend" / "css"

FONT_SIZE = re.compile(r"font-size\s*:\s*([^;}]+)[;}]")
DECLARATION = re.compile(r"(--[\w-]+)\s*:")
# var(--x) with no fallback. A fallback is a deliberate "may not exist".
VAR_NO_FALLBACK = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
COMMENTS = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(text):
    return COMMENTS.sub("", text)


@pytest.fixture(scope="module")
def sheets():
    """{name: source with comments removed}. Comments discuss px sizes and
    token names constantly; matching on them would be all false positives."""
    return {
        p.name: _strip_comments(p.read_text(encoding="utf-8"))
        for p in sorted(CSS_DIR.glob("*.css"))
    }


@pytest.fixture(scope="module")
def all_css(sheets):
    return "\n".join(sheets.values())


# ---------------- the type scale ----------------


def test_scale_tokens_exist_and_are_relative(sheets):
    tokens = re.findall(
        r"(--text-(?:2xs|xs|sm|base|lg|xl))\s*:\s*([^;]+);", sheets["tokens.css"]
    )
    found = {name: value.strip() for name, value in tokens}
    assert len(found) == 6, f"expected six scale steps, found {sorted(found)}"
    for name, value in found.items():
        assert value.endswith("rem"), f"{name} is {value!r}; the scale must be in rem"


def test_no_font_size_is_written_in_px(sheets):
    """
    The whole point of Phase 5.

    A `px` font-size ignores the browser's own font-size setting -- the
    control a low-vision reader actually reaches for, and the one that
    does not reflow the layout the way page zoom does. One `px` slipping
    back in is invisible until someone raises their font size and that
    element alone stays put.
    """
    offenders = []
    for name, source in sheets.items():
        for value in FONT_SIZE.findall(source):
            if re.search(r"\d\s*px", value):
                offenders.append(f"{name}: font-size: {value.strip()}")
    assert not offenders, "px font-sizes:\n  " + "\n  ".join(offenders)


ABSOLUTE_LENGTH = re.compile(r"\d\s*(px|pt|pc|cm|mm|in)\b")


def _drawn_from_the_scale(value):
    """
    True if `value` is `inherit`, a scale token, or a clamp() whose bounds
    are scale tokens.

    Written as "remove the tokens, then check nothing absolute is left"
    rather than as one pattern, because clamp() nests var() calls and a
    single regex cannot match balanced parentheses.
    """
    value = value.strip()
    if value == "inherit":
        return True
    if "--text-" not in value:
        return False
    remainder = re.sub(r"var\(\s*--text-[\w-]+\s*\)", "", value)
    # Viewport units and clamp()/calc() syntax may remain; an absolute
    # length or another custom property may not.
    return not ABSOLUTE_LENGTH.search(remainder) and "var(" not in remainder


def test_every_font_size_comes_from_the_scale(sheets):
    """Values written as literals drift; the eighteen separate `14px`
    declarations that preceded the scale are what this prevents."""
    offenders = [
        f"{name}: font-size: {value.strip()}"
        for name, source in sheets.items()
        for value in FONT_SIZE.findall(source)
        if not _drawn_from_the_scale(value)
    ]
    assert not offenders, "font-sizes not drawn from the scale:\n  " + "\n  ".join(
        offenders
    )


def test_nothing_sets_a_font_size_on_the_root(all_css):
    """Every `rem` in the app is relative to the root. Setting a size on
    it would rescale the entire interface and silently defeat the
    reader's own setting -- the opposite of what the scale is for."""
    for block in re.findall(r"(?:^|\})\s*(html|:root)[^{]*\{([^}]*)\}", all_css):
        assert "font-size" not in block[1], f"{block[0]} must not set font-size"


# ---------------- custom properties ----------------


def test_every_custom_property_used_is_defined(sheets, all_css):
    """
    An undefined `var(--x)` is silent: the declaration is simply dropped.

    Only bare `var(--x)` is checked. `var(--x, fallback)` is a deliberate
    statement that the property may be absent -- `--panel-accent` is set
    per panel at runtime and read that way on purpose.
    """
    defined = set(DECLARATION.findall(all_css))
    used = set(VAR_NO_FALLBACK.findall(all_css))
    missing = sorted(used - defined)
    assert not missing, f"custom properties used but never defined: {missing}"


# ---------------- adaptive rendering ----------------


def test_the_colour_scheme_is_declared(all_css):
    """The palette is light-only. Without saying so, UA widgets -- the
    range input, the text fields, the scrollbars -- may render dark on a
    system set to dark."""
    assert re.search(r"color-scheme\s*:\s*light", all_css), (
        "color-scheme: light is not declared"
    )


@pytest.mark.parametrize(
    "query",
    [
        "(prefers-reduced-motion: reduce)",
        "(forced-colors: active)",
        "(prefers-contrast: more)",
    ],
)
def test_the_preference_queries_are_present(all_css, query):
    assert f"@media {query}" in all_css, f"no @media {query} block"


def test_forced_colours_covers_everything_whose_background_is_data(all_css):
    """
    Forced-colours mode strips backgrounds.

    For an app that draws its readings as coloured boxes, that deletes
    the data and leaves the layout intact -- nothing looks broken enough
    to notice. Each selector below carries meaning in a background or a
    box-shadow and has to be restated in system colours or opted out.
    """
    block = re.search(
        r"@media\s*\(forced-colors:\s*active\)\s*\{(.*?)\n\}", all_css, re.DOTALL
    )
    assert block, "no forced-colors block"
    body = block.group(1)
    for selector in (
        ".emo-fill",
        ".emo-avg-mark",
        ".emo-track",
        ".person-swatch",
        ".job-bar-fill",
        ".person-row.is-selected",
        ".video-combo-item",
    ):
        assert selector in body, (
            f"{selector} carries meaning in a background but is not handled"
        )


def test_suppressed_outlines_have_a_forced_colours_fallback(sheets, all_css):
    """
    `outline: none` plus a `box-shadow` ring is fine until forced colours,
    which drops box shadows and would leave those controls with no focus
    indicator at all -- invisible until someone tries to use the app that
    way.
    """
    suppressed = set()
    for name, source in sheets.items():
        if name == "adaptive.css":
            continue
        for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", source):
            if re.search(r"outline\s*:\s*none", body):
                suppressed.update(
                    s.strip() for s in selector.split(",") if ":focus" in s
                )

    block = re.search(
        r"@media\s*\(forced-colors:\s*active\)\s*\{(.*?)\n\}", all_css, re.DOTALL
    )
    assert block, "no forced-colors block"
    body = block.group(1)

    missing = [s for s in suppressed if s.split(":")[0].strip() not in body]
    assert not missing, (
        "these suppress their outline but have no forced-colours fallback: "
        + str(sorted(missing))
    )


def test_more_contrast_only_repoints_tokens(all_css):
    """
    Deliberately a constraint, not a convenience.

    If raising contrast needs a per-rule change, some colour is being set
    outside the token layer -- and the fix is to move it in, not to add
    an exception here. The block staying token-only is the evidence the
    token layer is still doing its job.
    """
    block = re.search(
        r"@media\s*\(prefers-contrast:\s*more\)\s*\{(.*?)\n\}", all_css, re.DOTALL
    )
    assert block, "no prefers-contrast block"
    selectors = [s.strip() for s in re.findall(r"([^{}]+)\{", block.group(1))]
    assert selectors, "the prefers-contrast block is empty"
    assert set(selectors) == {":root"}, (
        f"prefers-contrast should only re-point tokens on :root, but styles {selectors}"
    )
