"""
Contrast assertions over the committed frontend palette.

Phase 0.1 of docs/accessibility-plan.md. The maths and the pair registry
live in tests/contrast_check.py; this file is only the policy.

The policy is a **known-failures baseline** rather than "nothing may
fail", because at the time this lands the audit's findings are all still
open -- asserting zero failures would put the suite red for the whole
length of Phases 1-5 and teach everyone to ignore it. Instead:

  * a failure that is not in KNOWN_FAILURES fails the suite. That is the
    regression guard: it catches a palette edit made during the
    remediation work that breaks something which was previously fine.

  * a KNOWN_FAILURES entry that now *passes* also fails the suite, with
    an instruction to delete it. That is what turns the baseline into a
    progress ledger: finishing Phase 3.2 is not done until its line is
    struck off here.

When the last entry is gone, delete the baseline and the two tests that
read it, and assert `failures() == []` directly.
"""

import pytest

import contrast_check


# (area, label) -> the plan section that clears it. Every entry is a
# real, confirmed defect; none of these are tolerated indefinitely.
KNOWN_FAILURES = {
    # -- Phase 3.1: readableTextColor()'s threshold sits far above the
    # true black/white crossover, so four of seven person colours get
    # white text on the filter chip when they need dark.
    ("person", "filter chip text on #e0a458"): "3.1",
    ("person", "filter chip text on #c77dff"): "3.1",
    ("person", "filter chip text on #f472b6"): "3.1",
    ("person", "filter chip text on #8b94a3"): "3.1",

    # -- Phase 3.2: rgba(255,255,255,0.75) over --signal (sidebar.css:174).
    ("sidebar", "score on selected row"): "3.2",

    # -- Phase 3.3: neither --border-soft nor the recessed fill marks a
    # text input as a field until it is focused.
    ("input", "resting border vs card"): "3.3",
    ("input", "resting border vs own fill"): "3.3",
    ("input", "input fill vs card"): "3.3",
    ("input", "dropdown border vs card"): "3.3",
    # Found by this checker rather than by the audit: --text-dim reads
    # 5.54:1 on the card and 4.95:1 on the page floor, but placeholders
    # sit on the recessed --surface-alt fill, where it lands at 4.48:1.
    # Marginal, but under 4.5 -- and it is the same element Phase 3.3
    # already opens, so it is cheapest to fix there.
    ("input", "placeholder on input fill"): "3.3",

    # -- Phase 3.4: the signed tracks' zero reference. The audit measured
    # --border-strong against the card (2.35:1); its real backdrop is the
    # groove fill, which is worse.
    ("emotions", "signed zero marker vs groove"): "3.4",
    # Also found by this checker: the groove itself is 1.24:1 against the
    # card, so the track's extent -- the thing a fill is read as a
    # proportion *of* -- has no perceivable boundary. Same token pair as
    # "input fill vs card" in a different role; Phase 3.4 should decide
    # whether the groove needs an edge or whether the fill's own 4.72:1
    # against it is sufficient.
    ("emotions", "groove vs card"): "3.4",

    # -- Phase 3.5: swatches are 1.35-2.73:1 on the row fill. The palette
    # must not be darkened (the same colours stroke boxes over video), so
    # the fix is a hairline ring, not a hue change.
    ("person", "swatch #49d3c8 on row fill"): "3.5",
    ("person", "swatch #49d3c8 on card"): "3.5",
    ("person", "swatch #e0a458 on row fill"): "3.5",
    ("person", "swatch #e0a458 on card"): "3.5",
    ("person", "swatch #c77dff on row fill"): "3.5",
    ("person", "swatch #c77dff on card"): "3.5",
    ("person", "swatch #7dd3fc on row fill"): "3.5",
    ("person", "swatch #7dd3fc on card"): "3.5",
    ("person", "swatch #f472b6 on row fill"): "3.5",
    ("person", "swatch #f472b6 on card"): "3.5",
    ("person", "swatch #a3e635 on row fill"): "3.5",
    ("person", "swatch #a3e635 on card"): "3.5",
    ("person", "swatch #8b94a3 on row fill"): "3.5",
}


@pytest.fixture(scope="module")
def results():
    return contrast_check.check()


# ---------------- the checker's own parsing ----------------
# If these break, every ratio below is measuring something other than
# what the app ships, so they are worth asserting independently.


def test_semantic_tokens_resolve_through_var_aliases(results):
    tokens = contrast_check.load_tokens()
    # --signal is var(--primary-500) is #006c98: two hops, and the shape
    # almost every semantic token in tokens.css takes.
    assert tokens["--signal"] == ((0x00, 0x6C, 0x98), 1.0)
    assert tokens["--bg"] == tokens["--surface-50"]
    assert tokens["--emotion"] == tokens["--primary-700"]


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
    assert palette[0] == "#49d3c8"
    assert palette[-1] == "#8b94a3"


def test_every_pair_resolves(results):
    """A typo in the registry would otherwise surface as a KeyError deep
    in a later assertion rather than as its own failure."""
    assert len(results) > 60
    for result in results:
        assert 1.0 <= result.ratio <= 21.0


# ---------------- the baseline policy ----------------


def test_no_contrast_failures_outside_the_baseline(results):
    unexpected = [
        r for r in results
        if r.status == "FAIL" and (r.pair.area, r.pair.label) not in KNOWN_FAILURES
    ]
    assert not unexpected, "new contrast failures:\n" + "\n".join(
        f"  {r.pair.area}/{r.pair.label}: {r.ratio:.2f} < {r.pair.requirement} "
        f"({r.pair.foreground} on {r.pair.background})"
        for r in unexpected
    )


def test_baseline_entries_are_still_failing(results):
    by_key = {(r.pair.area, r.pair.label): r for r in results}

    fixed = []
    missing = []
    for key, phase in KNOWN_FAILURES.items():
        result = by_key.get(key)
        if result is None:
            missing.append(f"  {key[0]}/{key[1]} (phase {phase}) is no longer a registered pair")
        elif result.status != "FAIL":
            fixed.append(f"  {key[0]}/{key[1]} (phase {phase}) now passes at {result.ratio:.2f}")

    assert not fixed and not missing, (
        "KNOWN_FAILURES is stale -- remove these entries:\n"
        + "\n".join(fixed + missing)
    )
