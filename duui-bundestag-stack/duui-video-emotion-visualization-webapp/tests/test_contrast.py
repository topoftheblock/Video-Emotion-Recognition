"""
Contrast assertions over the committed frontend palette.

Phase 0.1 of docs/accessibility-plan.md, tightened by Phase 3. The maths
and the pair registry live in tests/contrast_check.py; this file is only
the policy.

That policy used to be a KNOWN_FAILURES baseline of the 25 pairs the
audit found still open, because asserting zero while they were all live
would have kept the suite red for the length of the remediation. Phase 3
closed the last of them, so the baseline is gone and the assertion is
now the plain one: nothing below its threshold, ever.

Six pairs are recorded as INFO rather than asserted. Those are decisions,
not omissions -- each is argued at its call site (the panel dots and the
--border exemption in css/tokens.css, the emotion groove in
css/emotions.css, the input fill in contrast_check.py) and the checker
still prints their ratios so they stay visible.
"""

import pytest

import contrast_check


@pytest.fixture(scope="module")
def results():
    return contrast_check.check()


# ---------------- the checker's own parsing ----------------
# If these break, every ratio below is measuring something other than
# what the app ships, so they are worth asserting independently.


def test_semantic_tokens_resolve_through_var_aliases():
    tokens = contrast_check.load_tokens()
    # --signal is var(--primary-500) is #006c98: two hops, and the shape
    # almost every semantic token in tokens.css takes.
    assert tokens["--signal"] == ((0x00, 0x6C, 0x98), 1.0)
    assert tokens["--bg"] == tokens["--surface-50"]
    assert tokens["--emotion"] == tokens["--primary-700"]
    assert tokens["--border-input"] == tokens["--surface-400"]


def test_translucent_tokens_keep_their_alpha():
    tokens = contrast_check.load_tokens()
    assert tokens["--border-soft"] == ((102, 104, 114), 0.2)


def test_non_colour_declarations_are_skipped():
    tokens = contrast_check.load_tokens()
    for name in ("--theme-rounded-base", "--font-ui", "--transition", "--shadow-md"):
        assert name not in tokens, f"{name} is not a colour and must not be checked"


def test_person_palette_is_read_from_state_js():
    palette = contrast_check.load_person_colours()
    # Six assignable colours plus the unknown-person fallback.
    assert len(palette) == 7
    assert palette[0] == "#e69f00"
    assert palette[-1] == "#c8c8d0"


def test_every_pair_resolves(results):
    """A typo in the registry would otherwise surface as a KeyError deep
    in a later assertion rather than as its own failure."""
    assert len(results) > 60
    for result in results:
        assert 1.0 <= result.ratio <= 21.0


# ---------------- the policy ----------------


def test_no_contrast_failures(results):
    failing = [r for r in results if r.status == "FAIL"]
    assert not failing, "contrast failures:\n" + "\n".join(
        f"  {r.pair.area}/{r.pair.label}: {r.ratio:.2f} < {r.pair.requirement} "
        f"({r.pair.foreground} on {r.pair.background})"
        for r in failing
    )


def test_readable_text_color_clears_aa_for_every_person_colour():
    """
    Phase 3.1's regression guard, and the check that would have caught
    the original bug.

    readableTextColor() picks the filter chip's text colour per person at
    render time. It used to threshold on luminance at L > 0.45 -- far
    above the true crossover near 0.18 -- so four of the seven colours
    were handed white text at 2.2-3.1:1. Asserting the *outcome* for
    every palette entry is what makes that unrepeatable, including after
    a palette change.
    """
    palette = contrast_check.load_person_colours()
    pick = contrast_check._readable_text_color_impl()

    weak = []
    for colour in palette:
        rgb = contrast_check._parse_rgba(colour)[0]
        ratio = contrast_check.contrast(contrast_check._parse_rgba(pick(rgb))[0], rgb)
        if ratio < contrast_check.TEXT:
            weak.append(f"  {colour}: picked {pick(rgb)} at {ratio:.2f}:1")

    assert not weak, (
        f"readableTextColor() ({pick.description}) drops below "
        f"{contrast_check.TEXT}:1 on:\n" + "\n".join(weak)
    )
