"""
Two script-level invariants, both guarding bugs that actually shipped.

Neither is the kind of thing a linter catches: one is a missing space in
a template literal, the other a font family that was never bundled. Both
were invisible in the running app — the first only in what a screen
reader says, the second only in which typeface the canvas silently fell
back to.

Kept deliberately narrow. These assert the specific shape of two known
regressions rather than trying to analyze the JavaScript, because a
loose check over source text is a source of false alarms and these two
are worth having no false alarms about.
"""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"


def test_person_rows_separate_the_name_from_the_metadata() -> None:
    """
    A person row's accessible name is computed from its contents.

    With no whitespace between the name and the score span, the two
    concatenate: "person_1" + "100%" announces as "person eleven hundred
    percent". The fix is a single newline in the template, which is
    exactly the kind of thing a later edit removes without noticing.
    """
    people = (FRONTEND / "js" / "panels" / "people.js").read_text(encoding="utf-8")
    offenders = re.findall(r"\}<span class=\"person-meta\"", people)
    assert not offenders, (
        "a .person-meta span follows an interpolation with no separator; "
        "the row's accessible name will run the two values together"
    )


def test_canvas_text_uses_a_font_the_app_actually_ships() -> None:
    """
    Canvas text takes no part in the cascade: whatever family string is
    passed to ctx.font is used verbatim, and an unbundled name falls
    silently back to a generic.

    This asked for 'IBM Plex Mono' for a long time — a family this app
    has never shipped — so every on-video label rendered in the default
    monospace and nobody could see it from the page.
    """
    overlay = (FRONTEND / "js" / "playback" / "overlay.js").read_text(encoding="utf-8")
    bundled = set(
        re.findall(
            r'font-family:\s*"([^"]+)"',
            (FRONTEND / "css" / "base.css").read_text(encoding="utf-8"),
        )
    )
    assert bundled, "no @font-face families found in base.css"

    generic = {"monospace", "sans-serif", "serif", "system-ui", "cursive", "fantasy"}
    for declaration in re.findall(r"ctx\.font\s*=\s*[`\"']([^`\"']+)", overlay):
        families = re.findall(r'"([^"]+)"|\'([^\']+)\'', declaration)
        named = [a or b for a, b in families]
        unknown = [f for f in named if f not in bundled and f.lower() not in generic]
        assert not unknown, (
            f"ctx.font asks for {unknown}, which base.css does not @font-face. "
            f"Bundled families are {sorted(bundled)}"
        )


def test_canvas_label_size_is_derived_from_the_root_font_size() -> None:
    """
    Canvas text cannot inherit the rem scale, so it has to be
    recomputed. A literal pixel size here would make the one piece of
    type sitting *on* the data the only piece that ignores the reader's
    setting.
    """
    overlay = (FRONTEND / "js" / "playback" / "overlay.js").read_text(encoding="utf-8")
    assert "documentElement" in overlay and "fontSize" in overlay, (
        "overlay.js should read the root font size rather than hardcoding one"
    )
    for declaration in re.findall(r"ctx\.font\s*=\s*[`\"']([^`\"']+)", overlay):
        assert not re.search(r"\d+px", declaration), (
            f"ctx.font has a literal pixel size: {declaration!r}"
        )


def test_the_on_video_label_color_comes_from_the_shared_decision() -> None:
    """
    The tag drawn over each bounding box picks its text color the same
    way the filter chip does. It used to hardcode a near-black — a
    second, independent copy of the same decision, which happened to
    pass but had nothing keeping it passing when the palette changed.
    """
    overlay = (FRONTEND / "js" / "playback" / "overlay.js").read_text(encoding="utf-8")
    assert "readableTextColor" in overlay, (
        "overlay.js should route its label color through readableTextColor()"
    )
