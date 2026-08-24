"""
The person palette's separability under colour-vision deficiency.

Phase 3.7 of docs/accessibility.md. The simulation and the distance
maths live in tests/cvd_check.py; this file is the policy.

Why this is a test and not a judgement call: a person's colour is the
only thing linking a stroked box on the video to a name in the sidebar.
Putting the name into the on-video label is out of scope, so there is no
text channel to fall back on -- two palette entries that collapse under a
common deficiency make two people indistinguishable, silently, for
roughly one man in twelve. That is a property worth pinning down rather
than re-deriving by eye whenever someone likes a different blue.
"""

import cvd_check


def test_palette_is_read_from_state_js():
    palette = cvd_check.load_palette()
    assert len(palette) == 7
    assert palette[0] == "#e69f00"


def test_no_two_person_colours_converge_under_any_deficiency():
    convergent = cvd_check.convergent()
    assert not convergent, (
        f"palette pairs below dE2000 {cvd_check.MIN_SEPARATION} "
        "(indistinguishable on the video, with no text fallback):\n"
        + "\n".join(
            f"  {kind:13} {a} vs {b}: {de:.2f}" for kind, a, b, de in convergent
        )
    )


def test_unknown_person_grey_separates_from_every_assignable_colour():
    """
    The fallback is the entry most likely to collide: it is neutral, so
    every deficiency pushes muted colours towards it. It is separated by
    *lightness* rather than hue for exactly that reason -- lightness is
    the one axis a deficiency leaves intact -- so this asserts the
    property that choice was made to secure.
    """
    palette = cvd_check.load_palette()
    grey, colours = palette[-1], palette[:-1]

    rows = [r for r in cvd_check.separations(palette) if grey in (r[1], r[2])]
    worst = min(rows, key=lambda r: r[3])
    assert worst[3] >= cvd_check.MIN_SEPARATION, (
        f"{grey} collapses into {worst[1] if worst[2] == grey else worst[2]} "
        f"under {worst[0]}: dE2000 {worst[3]:.2f}"
    )
    assert len(colours) == 6


def test_simulation_is_a_no_op_for_a_neutral_colour():
    """Sanity check on the matrices: greys carry no hue to lose, so every
    model should return one essentially unchanged. Guards against a
    transposed or mis-typed matrix, which would otherwise show up as
    plausible-looking but wrong separations."""
    for kind in cvd_check.CVD_MATRICES:
        out = cvd_check.simulate((128, 128, 128), kind)
        assert all(abs(c - 128) <= 6 for c in out), (
            f"{kind} moved a neutral grey to {out}"
        )
