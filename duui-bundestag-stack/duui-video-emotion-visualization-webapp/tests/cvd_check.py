"""
Colour-vision-deficiency separability for the person palette.

Phase 3.7 of docs/accessibility.md. The six PERSON_COLORS (plus the
unknown-person grey) are assigned to people at runtime and used in two
places: a swatch beside a name in the sidebar, and the stroke around
that person's face in the video. Nothing else links the two.

Because putting the name into the on-video label is out of scope, **hue
is the only channel** carrying that mapping. Two palette entries that
collapse into each other under a common colour-vision deficiency make
two people indistinguishable on the video, with no text fallback to
recover from -- so the palette's separability is load-bearing rather
than cosmetic, and worth a test rather than an eyeball.

Method: Machado, Oliveira & Fernandes (2009) severity-1.0 matrices,
applied in linear RGB, then CIEDE2000 between the simulated pairs.
CIEDE2000 rather than plain Euclidean dE76 because the palette is
saturated, which is exactly where dE76 overstates differences.

Standalone report (stdlib only):

    python3 tests/cvd_check.py
"""

import math
import re
from pathlib import Path

STATE_JS = Path(__file__).resolve().parent.parent / "src" / "frontend" / "js" / "state.js"

# Machado et al. (2009), severity 1.0. Row-major, operating on linear RGB.
CVD_MATRICES = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}

# CIEDE2000 below which two swatches of this size read as "the same
# colour" at a glance. The literature's just-noticeable difference is
# ~1-2 for large adjacent patches; these are 9px squares scattered down
# a list and 2px strokes over moving video, compared from memory rather
# than side by side, so the bar has to be far higher. 10 is the working
# floor -- comfortably above JND, and low enough that it only fires on
# pairs that genuinely converge.
MIN_SEPARATION = 10.0


def _to_linear(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c):
    c = max(0.0, min(1.0, c))
    v = 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return round(v * 255)


def parse_hex(value):
    v = value.lstrip("#")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, c)):02x}" for c in rgb)


def simulate(rgb, kind):
    """`rgb` as seen with `kind`, via Machado severity-1.0 in linear RGB."""
    matrix = CVD_MATRICES[kind]
    lin = [_to_linear(c) for c in rgb]
    out = [sum(m * v for m, v in zip(row, lin)) for row in matrix]
    return tuple(_to_srgb(c) for c in out)


# ---------------- CIELAB + CIEDE2000 ----------------

# D65, 2-degree observer.
_WHITE = (0.95047, 1.00000, 1.08883)


def to_lab(rgb):
    r, g, b = (_to_linear(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / _WHITE[0]
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / _WHITE[1]
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / _WHITE[2]

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def ciede2000(lab1, lab2):
    """CIE Delta E 2000. Follows Sharma, Wu & Dalal's formulation."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    avg_l = (l1 + l2) / 2
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    avg_c = (c1 + c2) / 2

    g = 0.5 * (1 - math.sqrt(avg_c ** 7 / (avg_c ** 7 + 25 ** 7))) if avg_c else 0.0
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    avg_cp = (c1p + c2p) / 2

    def hue(ap, bp):
        if ap == 0 and bp == 0:
            return 0.0
        h = math.degrees(math.atan2(bp, ap))
        return h + 360 if h < 0 else h

    h1p, h2p = hue(a1p, b1), hue(a2p, b2)

    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360

    dlp = l2 - l1
    dcp = c2p - c1p
    dhp_term = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2)

    if c1p * c2p == 0:
        avg_hp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        avg_hp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        avg_hp = (h1p + h2p + 360) / 2
    else:
        avg_hp = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(avg_hp - 30))
        + 0.24 * math.cos(math.radians(2 * avg_hp))
        + 0.32 * math.cos(math.radians(3 * avg_hp + 6))
        - 0.20 * math.cos(math.radians(4 * avg_hp - 63))
    )

    sl = 1 + (0.015 * (avg_l - 50) ** 2) / math.sqrt(20 + (avg_l - 50) ** 2)
    sc = 1 + 0.045 * avg_cp
    sh = 1 + 0.015 * avg_cp * t
    rt = (
        -2
        * math.sqrt(avg_cp ** 7 / (avg_cp ** 7 + 25 ** 7))
        * math.sin(math.radians(60 * math.exp(-(((avg_hp - 275) / 25) ** 2))))
    ) if avg_cp else 0.0

    return math.sqrt(
        (dlp / sl) ** 2
        + (dcp / sc) ** 2
        + (dhp_term / sh) ** 2
        + rt * (dcp / sc) * (dhp_term / sh)
    )


# ---------------- the palette under each deficiency ----------------


def load_palette(path=STATE_JS):
    """PERSON_COLORS plus UNKNOWN_PERSON_COLOR, in assignment order."""
    source = path.read_text(encoding="utf-8")
    block = re.search(r"PERSON_COLORS\s*=\s*\[(.*?)\]", source, re.DOTALL)
    palette = re.findall(r'"(#[0-9a-fA-F]{6})"', block.group(1)) if block else []
    unknown = re.search(r'UNKNOWN_PERSON_COLOR\s*=\s*"(#[0-9a-fA-F]{6})"', source)
    if unknown:
        palette.append(unknown.group(1))
    return palette


def separations(palette=None):
    """
    Every unordered pair, under normal vision and each deficiency, as
    [(kind, a, b, delta_e)] sorted worst-first.
    """
    palette = load_palette() if palette is None else palette
    rows = []
    for kind in ("normal",) + tuple(CVD_MATRICES):
        for i, first in enumerate(palette):
            for second in palette[i + 1:]:
                if kind == "normal":
                    sim_a, sim_b = parse_hex(first), parse_hex(second)
                else:
                    sim_a = simulate(parse_hex(first), kind)
                    sim_b = simulate(parse_hex(second), kind)
                rows.append((kind, first, second, ciede2000(to_lab(sim_a), to_lab(sim_b))))
    return sorted(rows, key=lambda r: r[3])


def convergent(palette=None, threshold=MIN_SEPARATION):
    return [r for r in separations(palette) if r[3] < threshold]


def _main():
    palette = load_palette()
    print(f"palette ({len(palette)}): {' '.join(palette)}\n")

    for kind in ("normal",) + tuple(CVD_MATRICES):
        print(f"-- {kind} " + "-" * (58 - len(kind)))
        if kind != "normal":
            print("   " + "  ".join(f"{c}->{to_hex(simulate(parse_hex(c), kind))}" for c in palette[:4]))
            print("   " + "  ".join(f"{c}->{to_hex(simulate(parse_hex(c), kind))}" for c in palette[4:]))
        rows = [r for r in separations(palette) if r[0] == kind][:6]
        for _, a, b, de in rows:
            flag = "  <-- CONVERGES" if de < MIN_SEPARATION else ""
            print(f"   dE2000 {de:6.2f}   {a}  vs  {b}{flag}")
        print()

    bad = convergent(palette)
    print(f"{len(bad)} pair(s) below dE2000 {MIN_SEPARATION}")
    for kind, a, b, de in bad:
        print(f"  {kind:13} {a} vs {b}: {de:.2f}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(_main())
