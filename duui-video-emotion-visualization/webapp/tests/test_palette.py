"""The person palette's separability under color-vision deficiency.

The simulation and the distance arithmetic live in `cvd_check.py`; this
file is the policy. See "Color and contrast" in docs/accessibility.md.

Why this is a test rather than a judgment call: a person's color is
the only thing linking a stroked box on the video to a name in the
sidebar. Putting the name into the on-video label is out of scope, so
there is no text channel to fall back on. Two palette entries that
collapse under a common deficiency make two people indistinguishable,
silently, for a substantial share of viewers. That is worth pinning
down rather than re-deriving by eye whenever someone prefers a
different blue.
"""

from support import cvd_check


def test_palette_is_read_from_state_js() -> None:
    """The palette under test is the one the frontend actually uses."""
    palette = cvd_check.load_palette()
    assert len(palette) == 7
    assert palette[0] == "#e69f00"


def test_no_two_person_colors_converge_under_any_deficiency() -> None:
    """No two assignable colors collapse together under any model."""
    convergent = cvd_check.convergent()
    assert not convergent, (
        f"palette pairs below dE2000 {cvd_check.MIN_SEPARATION} "
        "(indistinguishable on the video, with no text fallback):\n"
        + "\n".join(
            f"  {kind:13} {a} vs {b}: {de:.2f}" for kind, a, b, de in convergent
        )
    )


def test_unknown_person_gray_separates_from_every_assignable_color() -> None:
    """The fallback stays distinct from every color it sits beside.

    It is the entry most likely to collide, being neutral: every
    deficiency pushes muted colors toward it. It is separated by
    *lightness* rather than hue for that reason — lightness is the one
    axis a deficiency leaves intact — so this asserts the property that
    choice was made to secure.
    """
    palette = cvd_check.load_palette()
    gray, colors = palette[-1], palette[:-1]

    rows = [r for r in cvd_check.separations(palette) if gray in (r[1], r[2])]
    worst = min(rows, key=lambda r: r[3])
    assert worst[3] >= cvd_check.MIN_SEPARATION, (
        f"{gray} collapses into {worst[1] if worst[2] == gray else worst[2]} "
        f"under {worst[0]}: dE2000 {worst[3]:.2f}"
    )
    assert len(colors) == 6


def test_simulation_is_a_no_op_for_a_neutral_color() -> None:
    """A gray survives every simulation, which checks the matrices.

    Grays carry no hue to lose, so every model should return one
    essentially unchanged. This catches a transposed or mistyped
    matrix, which would otherwise show up as plausible-looking but
    wrong separations.
    """
    for kind in cvd_check.CVD_MATRICES:
        out = cvd_check.simulate((128, 128, 128), kind)
        assert all(abs(c - 128) <= 6 for c in out), (
            f"{kind} moved a neutral gray to {out}"
        )
