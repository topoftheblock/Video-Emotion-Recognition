"""A WCAG contrast checker for the frontend's palette.

Reads the committed colours out of `css/tokens.css` and `js/state.js`
and reports the contrast ratio of every pair the page actually
composites, so a palette change that breaks a threshold fails a check
rather than someone's eyes. See "Colour and contrast" in
docs/accessibility.md.

Two things make this more than a ratio between two colours:

- **Alpha.** Several of the colours are translucent: the subtitle box is
  black at 85% over arbitrary video, the selected person's score is
  white at 75% over the signal colour, and a soft border is a surface
  tone at 20%. A pair like that is only measurable once flattened
  against its real backdrop, which is why every side of a pair here is a
  *stack* of layers rather than one colour.

- **Colours computed at runtime.** `readableTextColor` in `state.js`
  picks the filter chip's text colour per person as it renders, so the
  pair that matters is whatever that function returns against that
  person's colour, not anything written literally in a stylesheet.
  `_readable_text_color_impl` mirrors it from the parsed source.

The registry of pairs is curated rather than discovered: nothing in the
stylesheets says which colours end up stacked on which. A new
combination has to be added here, or it is not checked.

For a standalone report, needing nothing but the standard library:

    python3 tests/contrast_check.py

The assertions live in `test_contrast.py`.
"""

import re
from pathlib import Path
from typing import Protocol

#: One opaque colour, as 0-255 channels.
RGB = tuple[int, int, int]


class TextColorPicker(Protocol):
    """A stand-in for `readableTextColor`, parsed out of the source.

    Callable like the function it mirrors, and carrying a description of
    *which* form was found, so a report can say what it measured.
    """

    description: str

    def __call__(self, rgb: RGB) -> str:
        """Return the text colour this picker would choose."""


FRONTEND = Path(__file__).resolve().parent.parent / "src" / "frontend"
TOKENS_CSS = FRONTEND / "css" / "tokens.css"
STATE_JS = FRONTEND / "js" / "state.js"

# WCAG 2.2 minimums. LARGE applies at 18.66px bold or 24px and above; UI
# is the non-text minimum, for anything conveying meaning or marking a
# control's boundary. INFO records a pair without asserting on it, for
# colours deliberately exempted — so the decision stays visible rather
# than becoming a silent omission.
TEXT = 4.5
LARGE = 3.0
UI = 3.0
INFO = None

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


# Colour maths.


def _srgb_channel(value: int) -> float:
    """Linearize one 0-255 channel, as WCAG's formula defines it."""
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: RGB) -> float:
    """Return the relative luminance of an opaque colour."""
    r, g, b = (_srgb_channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: RGB, bg: RGB) -> float:
    """Return the contrast ratio between two opaque colours."""
    a, b = luminance(fg), luminance(bg)
    if a < b:
        a, b = b, a
    return (a + 0.05) / (b + 0.05)


def composite(fg: RGB, alpha: float, bg: RGB) -> RGB:
    """Paint `fg` at `alpha` over opaque `bg`, source-over."""
    r, g, b = (
        round(f * a + q * (1 - a))
        for f, q, a in (
            (fg[0], bg[0], alpha),
            (fg[1], bg[1], alpha),
            (fg[2], bg[2], alpha),
        )
    )
    return (r, g, b)


# Parsing the committed sources.

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB = re.compile(
    r"^rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)\s*(?:[,/]\s*([\d.]+)\s*)?\)$"
)
_VAR = re.compile(r"^var\(\s*(--[\w-]+)\s*\)$")
# Only whole-value declarations are colours we can use. A shadow ("0 1px
# 2px rgba(...)"), a font stack or a length lands here too and is
# skipped — matching the *entire* value is what rejects them.
_DECL = re.compile(r"^\s*(--[\w-]+)\s*:\s*([^;]+);", re.MULTILINE)


def _parse_rgba(text: str) -> tuple[RGB, float] | None:
    """Parse one colour value into its channels and its alpha.

    Args:
        text: A whole CSS value.

    Returns:
        The colour and its alpha, or None if the value is not a plain
        colour — a shadow, a font stack or a length.
    """
    text = text.strip()

    hex_match = _HEX.match(text)
    if hex_match:
        digits = hex_match.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
        return (r, g, b), 1.0

    rgb_match = _RGB.match(text)
    if rgb_match:
        red, green, blue, alpha = rgb_match.groups()
        channels = (round(float(red)), round(float(green)), round(float(blue)))
        return channels, float(alpha) if alpha else 1.0

    return None


def load_tokens(path: Path = TOKENS_CSS) -> dict[str, tuple[RGB, float]]:
    """
    Every custom property in tokens.css that resolves to a single
    colour, as {name: ((r, g, b), alpha)}.

    var() aliases are followed, which is the whole point: the semantic
    half of tokens.css is almost entirely `--signal:
    var(--primary-500)`, so a checker that only read literals would see
    none of the names the stylesheets actually use.
    """
    source = path.read_text(encoding="utf-8")
    raw = {name: value.strip() for name, value in _DECL.findall(source)}

    resolved: dict[str, tuple[RGB, float]] = {}

    def resolve(name: str, seen: tuple = ()) -> tuple[RGB, float] | None:
        """Follow one name to a colour, through any var() aliases."""
        if name in resolved:
            return resolved[name]
        if name in seen or name not in raw:
            return None
        value = raw[name]

        alias = _VAR.match(value)
        if alias:
            target = resolve(alias.group(1), seen + (name,))
            if target is not None:
                resolved[name] = target
            return target

        colour = _parse_rgba(value)
        if colour is not None:
            resolved[name] = colour
        return colour

    for name in raw:
        resolve(name)
    return resolved


def load_person_colours(path: Path = STATE_JS) -> list[str]:
    """
    PERSON_COLORS plus UNKNOWN_PERSON_COLOR from js/state.js.

    These are not in tokens.css and cannot be: they are assigned to
    people at runtime by assignPersonColors(), and the same six values
    are used both as sidebar swatches on a light surface and as stroke
    colours over arbitrary video. Two very different contrast questions,
    same list.
    """
    source = path.read_text(encoding="utf-8")

    block = re.search(r"PERSON_COLORS\s*=\s*\[(.*?)\]", source, re.DOTALL)
    palette = re.findall(r'"(#[0-9a-fA-F]{6})"', block.group(1)) if block else []

    unknown = re.search(r'UNKNOWN_PERSON_COLOR\s*=\s*"(#[0-9a-fA-F]{6})"', source)
    if unknown:
        palette.append(unknown.group(1))
    return palette


def _readable_text_color_impl(path: Path = STATE_JS) -> TextColorPicker:
    """
    Mirror readableTextColor() from js/state.js.

    Parsed rather than hardcoded, so it tracks whichever form the
    source is in. Two are understood:

      * `L > <threshold> ? "<dark>" : "<light>"` — a fixed luminance
        threshold. One well above the true black-and-white crossover
        picks the wrong text colour for the colours in between, which is
        the bug this mirror exists to catch.
      * anything else — assumed to be the fixed form, emulated as "pick
        whichever of the function's two hex literals contrasts better",
        which is what the replacement is specified to do.
    """
    source = path.read_text(encoding="utf-8")
    match = re.search(
        r"export function readableTextColor\s*\([^)]*\)\s*\{(.*?)\n\}",
        source,
        re.DOTALL,
    )
    body = match.group(1) if match else ""

    candidates = re.findall(r'"(#[0-9a-fA-F]{6})"', body)
    threshold = re.search(
        r"return\s+L\s*>\s*([\d.]+)\s*\?\s*"
        r'"(#[0-9a-fA-F]{6})"\s*:\s*"(#[0-9a-fA-F]{6})"',
        body,
    )

    if threshold:
        cut, dark, light = (
            float(threshold.group(1)),
            threshold.group(2),
            threshold.group(3),
        )

        def pick(rgb: RGB) -> str:
            """Choose by luminance, the way the threshold form does."""
            return dark if luminance(rgb) > cut else light

        # The description rides on the function, which is what the
        # report and the assertions read it from.
        pick.description = f"threshold L > {cut}"  # type: ignore[attr-defined]
        return pick  # type: ignore[return-value]

    options = candidates or ["#0b0e14", "#ffffff"]

    def by_contrast(rgb: RGB) -> str:
        """Choose whichever candidate contrasts better."""

        def ratio(hex_value: str) -> float:
            """The contrast of one candidate against this colour."""
            parsed = _parse_rgba(hex_value)
            assert parsed is not None
            return contrast(parsed[0], rgb)

        return max(options, key=ratio)

    description = "max contrast of " + ", ".join(options)
    by_contrast.description = description  # type: ignore[attr-defined]
    return by_contrast  # type: ignore[return-value]


# The pair registry.


class Layer:
    """
    One side of a pair, as a stack of colours painted bottom-first.

    A single opaque token is the common case (`Layer("--signal")`), but
    anything translucent needs what is underneath it to mean anything —
    `Layer("--signal", "rgba(255,255,255,0.75)")` is the selected person
    row's score text, and it is only 3.99:1 once flattened.
    """

    def __init__(self, *specs: str) -> None:
        """Record the layers, bottom-first."""
        self.specs = specs

    def flatten(self, tokens: dict[str, tuple[RGB, float]], base: RGB = WHITE) -> RGB:
        """Paint the stack over `base` and return the resulting colour.

        Raises:
            KeyError: If a layer names a colour that cannot be resolved.
        """
        rgb = base
        for spec in self.specs:
            colour = tokens[spec] if spec in tokens else _parse_rgba(spec)
            if colour is None:
                raise KeyError(f"unknown colour spec: {spec!r}")
            fg, alpha = colour
            rgb = fg if alpha >= 1.0 else composite(fg, alpha, rgb)
        return rgb

    def __str__(self) -> str:
        """Describe the stack top-first, the way a reader reads it."""
        return " over ".join(reversed(self.specs))


class Pair:
    """One foreground-over-background pair, and what it must reach."""

    def __init__(
        self,
        area: str,
        label: str,
        foreground: "Layer",
        background: "Layer",
        requirement: float | None,
    ) -> None:
        """Record the pair, and the minimum ratio it must meet."""
        self.area = area
        self.label = label
        self.foreground = foreground
        self.background = background
        self.requirement = requirement


def _static_pairs() -> list[Pair]:
    """
    Pairs written literally in the stylesheets. Grouped by the area of
    the UI they belong to so a failure names somewhere to go and look.
    """
    P = Pair
    return [
        # Body copy on the two page surfaces.
        P("base", "--text on card", Layer("--text"), Layer("--surface"), TEXT),
        P("base", "--text on page floor", Layer("--text"), Layer("--bg"), TEXT),
        P("base", "--text-dim on card", Layer("--text-dim"), Layer("--surface"), TEXT),
        P("base", "--text-dim on page floor", Layer("--text-dim"), Layer("--bg"), TEXT),
        P(
            "base",
            "--text-strong on card",
            Layer("--text-strong"),
            Layer("--surface"),
            TEXT,
        ),
        P(
            "base",
            "--text-strong on --surface-50",
            Layer("--text-strong"),
            Layer("--surface-50"),
            TEXT,
        ),
        P(
            "base",
            "::selection text on --signal-soft",
            Layer("--signal-strong"),
            Layer("--signal-soft"),
            TEXT,
        ),
        # Text inputs (Ask + video combobox). The fill is recessed, so
        # the placeholder's backdrop is --surface-alt and not the card
        # behind it.
        P(
            "input",
            "placeholder on input fill",
            Layer("--text-placeholder"),
            Layer("--surface-alt"),
            TEXT,
        ),
        P(
            "input",
            "typed text on input fill",
            Layer("--text"),
            Layer("--surface-alt"),
            TEXT,
        ),
        P(
            "input",
            "resting border vs card",
            Layer("--border-input"),
            Layer("--surface"),
            UI,
        ),
        P(
            "input",
            "resting border vs own fill",
            Layer("--border-input"),
            Layer("--surface-alt"),
            UI,
        ),
        # The fill stopped having to carry the boundary the moment the
        # border above started to. Kept as INFO because it is the reason
        # that border exists, not because it is still a requirement.
        P(
            "input",
            "input fill vs card",
            Layer("--surface-alt"),
            Layer("--surface"),
            INFO,
        ),
        P("input", "focus ring on card", Layer("--signal"), Layer("--surface"), UI),
        P(
            "input",
            "dropdown border vs card",
            Layer("--border-input"),
            Layer("--surface"),
            UI,
        ),
        # Buttons and chips.
        P(
            "button",
            "primary button label",
            Layer("#ffffff"),
            Layer("--gradient-brand"),
            TEXT,
        ),
        P(
            "button",
            "primary button hover label",
            Layer("#ffffff"),
            Layer("--signal-hover"),
            TEXT,
        ),
        P(
            "button",
            "neutral button label at rest",
            Layer("--text-dim"),
            Layer("--surface"),
            TEXT,
        ),
        P("button", "focus ring on card", Layer("--signal"), Layer("--surface"), UI),
        # .person-row:focus-visible sits on a selected (--signal) row,
        # but outline-offset: 2px lifts the ring clear onto the panel
        # behind it. That offset is load-bearing: without it the ring
        # would be --signal on --signal.
        P(
            "button",
            "focus ring clear of selected row",
            Layer("--signal"),
            Layer("--surface"),
            UI,
        ),
        P(
            "chip",
            "overlay tag / filter chip text",
            Layer("--signal-strong"),
            Layer("--signal-soft"),
            TEXT,
        ),
        # Sidebar person lists.
        P("sidebar", "panel title", Layer("--text-dim"), Layer("--surface"), TEXT),
        P(
            "sidebar",
            "person name on row fill",
            Layer("--text"),
            Layer("--surface-50"),
            TEXT,
        ),
        P(
            "sidebar",
            "person name on hover row",
            Layer("--signal-strong"),
            Layer("--signal-soft"),
            TEXT,
        ),
        P(
            "sidebar",
            "person name on selected row",
            Layer("#ffffff"),
            Layer("--signal"),
            TEXT,
        ),
        # The alpha is duplicated from css/sidebar.css rather than
        # read from it — the one literal in this file that can drift
        # from the stylesheet it describes, so the two have to move
        # together.
        P(
            "sidebar",
            "score on selected row",
            Layer("--signal", "rgba(255,255,255,0.85)"),
            Layer("--signal"),
            TEXT,
        ),
        P(
            "sidebar",
            "cross-video detail text",
            Layer("--surface-500"),
            Layer("--surface-50"),
            TEXT,
        ),
        P("sidebar", "empty hint", Layer("--text-dim"), Layer("--surface"), TEXT),
        # Emotion panels.
        P(
            "emotions",
            "dominant emotion label",
            Layer("--emotion"),
            Layer("--surface"),
            TEXT,
        ),
        P("emotions", "row label", Layer("--text-strong"), Layer("--surface"), TEXT),
        P("emotions", "legend header", Layer("--text-dim"), Layer("--surface"), TEXT),
        P("emotions", "live value", Layer("--text"), Layer("--surface"), TEXT),
        P("emotions", "average value", Layer("--text-dim"), Layer("--surface"), TEXT),
        P(
            "emotions",
            "track fill vs groove",
            Layer("--emotion-fill"),
            Layer("--surface-alt"),
            UI,
        ),
        P(
            "emotions",
            "average marker vs groove",
            Layer("--text-dim"),
            Layer("--surface-alt"),
            UI,
        ),
        # The signed tracks' zero reference — a value is read relative
        # to it, so it is not decoration. Its backdrop is the groove
        # fill, not the card (css/emotions.css:119).
        P(
            "emotions",
            "signed zero marker vs groove",
            Layer("--border-input"),
            Layer("--surface-alt"),
            UI,
        ),
        # Exempt, and deliberately so — see the comment on .emo-track in
        # css/emotions.css. Every row prints its live value and average
        # as text beside the bar, so the track is a second reading of a
        # number already written down rather than a graphic required to
        # understand anything. Recorded rather than deleted so the
        # decision stays visible.
        P(
            "emotions",
            "groove vs card",
            Layer("--surface-alt"),
            Layer("--surface"),
            INFO,
        ),
        # The video stage. Subtitles sit on rgba(0,0,0,0.85) over
        # whatever the video is showing. White footage is the worst case
        # for the box, so that is what is checked — anything darker only
        # helps.
        P(
            "stage",
            "subtitle text over palest video",
            Layer("#ffffff", "rgba(0,0,0,0.85)", "#ffffff"),
            Layer("#ffffff", "rgba(0,0,0,0.85)"),
            LARGE,
        ),
        P(
            "stage",
            "subtitle emotion over palest video",
            Layer("#ffffff", "rgba(0,0,0,0.85)", "--emotion-on-dark"),
            Layer("#ffffff", "rgba(0,0,0,0.85)"),
            TEXT,
        ),
        P(
            "stage",
            "empty state title",
            Layer("#ffffff"),
            Layer("--surface-700"),
            LARGE,
        ),
        P(
            "stage",
            "empty state detail",
            Layer("--surface-700", "rgba(255,255,255,0.72)"),
            Layer("--surface-700"),
            TEXT,
        ),
        P(
            "stage",
            "empty state command",
            Layer("#ffffff"),
            Layer("--surface-700", "rgba(255,255,255,0.1)"),
            TEXT,
        ),
        P(
            "stage",
            "transport time read-out",
            Layer("--text-dim"),
            Layer("--surface"),
            TEXT,
        ),
        P("stage", "CC toggle at rest", Layer("--text-dim"), Layer("--surface"), TEXT),
        P("stage", "CC toggle when on", Layer("#ffffff"), Layer("--signal"), TEXT),
        # Status and jobs.
        P("status", "ask error text", Layer("--danger-text"), Layer("--surface"), TEXT),
        P(
            "status",
            "stale job elapsed on banner",
            Layer("--error-800"),
            Layer("--danger-soft"),
            TEXT,
        ),
        P(
            "status",
            "job detail text",
            Layer("--text-strong"),
            Layer("--surface"),
            TEXT,
        ),
        P("status", "job title text", Layer("--text"), Layer("--surface"), TEXT),
        P(
            "status",
            "job progress fill vs groove",
            Layer("--gradient-brand"),
            Layer("--surface-alt"),
            UI,
        ),
        # Topbar.
        P(
            "topbar",
            "brand mark label",
            Layer("#ffffff"),
            Layer("--gradient-brand"),
            TEXT,
        ),
        P("topbar", "brand title", Layer("--text"), Layer("--surface-50"), TEXT),
        P("topbar", "picker label", Layer("--text-dim"), Layer("--surface-50"), TEXT),
        P("topbar", "dropdown option text", Layer("--text"), Layer("--surface"), TEXT),
        P(
            "topbar",
            "highlighted option text",
            Layer("--signal-strong"),
            Layer("--signal-soft"),
            TEXT,
        ),
        P("topbar", "missing-file note", Layer("--text-dim"), Layer("--surface"), TEXT),
        # Decorative, recorded but not asserted. Panel dots each sit
        # beside a text label naming the same panel, so colour is not
        # the sole channel and 1.4.11 does not apply. Recorded so the
        # exemption is visible rather than assumed.
        P(
            "decorative",
            "dot-emotion on card",
            Layer("--accent-emotion"),
            Layer("--surface"),
            INFO,
        ),
        P(
            "decorative",
            "dot-people on card",
            Layer("--accent-people"),
            Layer("--surface"),
            INFO,
        ),
        P(
            "decorative",
            "dot-live on card",
            Layer("--accent-live"),
            Layer("--surface"),
            INFO,
        ),
        P(
            "decorative",
            "dot-cross on card",
            Layer("--accent-cross"),
            Layer("--surface"),
            INFO,
        ),
        # Panel and topbar hairlines separate regions that are already
        # separated by spacing and fill — purely decorative under
        # 1.4.11.
        P(
            "decorative",
            "panel border on card",
            Layer("--border"),
            Layer("--surface"),
            INFO,
        ),
        P(
            "decorative",
            "topbar hairline",
            Layer("--border"),
            Layer("--surface-50"),
            INFO,
        ),
    ]


def _person_pairs(palette: list[str], pick_text: TextColorPicker) -> list[Pair]:
    """
    Where a person's colour carries meaning, and what actually has to
    clear a threshold for it to do so.

    Not the colours themselves. The same six are stroked over arbitrary
    video, where they have to stay bright, which leaves them at
    1.4-2.7:1 against the light rows in the sidebar — and darkening them
    to fix that would break the other use. The swatch's boundary is a
    ring for that reason, so the ring is what is asserted here;
    the raw colour-on-surface figures stay as INFO, because they are the
    reason the ring exists and would otherwise look like an omission.

    The overlay stroke over footage is not checked at all: its backdrop
    is whatever the video is showing, so there is no ratio to compute —
    only the palette's separability under colour-vision deficiency,
    which is tests/cvd_check.py's job.
    """
    pairs = [
        Pair(
            "person",
            "swatch ring on row fill",
            Layer("--border-input"),
            Layer("--surface-50"),
            UI,
        ),
        Pair(
            "person",
            "swatch ring on card",
            Layer("--border-input"),
            Layer("--surface"),
            UI,
        ),
        Pair(
            "person",
            "swatch ring on hovered row",
            Layer("--border-input"),
            Layer("--signal-soft"),
            UI,
        ),
        # White, because --border-input against --signal is 1.05:1.
        Pair(
            "person",
            "swatch ring on selected row",
            Layer("#ffffff"),
            Layer("--signal"),
            UI,
        ),
    ]
    for colour in palette:
        pairs.append(
            Pair(
                "person",
                f"swatch {colour} on row fill (ringed)",
                Layer(colour),
                Layer("--surface-50"),
                INFO,
            )
        )
    for colour in palette:
        parsed = _parse_rgba(colour)
        assert parsed is not None, f"palette entry is not a colour: {colour}"
        rgb = parsed[0]
        pairs.append(
            Pair(
                "person",
                f"filter chip text on {colour}",
                Layer(pick_text(rgb)),
                Layer(colour),
                TEXT,
            )
        )
    return pairs


# Running the check.


class Result:
    """One measured pair: what it reached, and against what."""

    def __init__(
        self, pair: Pair, ratio: float, foreground: RGB, background: RGB
    ) -> None:
        """Record the measurement and the colours it was taken from."""
        self.pair = pair
        self.ratio = ratio
        self.foreground = foreground
        self.background = background

    @property
    def status(self) -> str:
        """PASS, FAIL, or INFO for a pair with no threshold."""
        if self.pair.requirement is None:
            return "INFO"
        return "PASS" if self.ratio >= self.pair.requirement else "FAIL"

    def __str__(self) -> str:
        """Format one line of the standalone report."""
        need = (
            "     -"
            if self.pair.requirement is None
            else f"{self.pair.requirement:6.1f}"
        )
        return (
            f"{self.status:4}  {self.ratio:6.2f}  need {need}  "
            f"{self.pair.area:10}  {self.pair.label}"
        )


def check() -> list[Result]:
    """Measure every registered pair against the committed sources."""
    tokens = load_tokens()
    palette = load_person_colours()
    pick_text = _readable_text_color_impl()

    results = []
    for pair in _static_pairs() + _person_pairs(palette, pick_text):
        background = pair.background.flatten(tokens)
        foreground = pair.foreground.flatten(tokens, base=background)
        results.append(
            Result(pair, contrast(foreground, background), foreground, background)
        )
    return results


def failures(results: list[Result] | None = None) -> list[Result]:
    """Return only the pairs that fell below their requirement."""
    results = check() if results is None else results
    return [r for r in results if r.status == "FAIL"]


def _main() -> int:
    """Print the full report, grouped by area of the interface."""
    results = check()
    pick_text = _readable_text_color_impl()

    print(f"tokens:            {TOKENS_CSS}")
    print(f"person palette:    {STATE_JS}")
    print(f"readableTextColor: {pick_text.description}")
    print()

    area = None
    for result in results:
        if result.pair.area != area:
            area = result.pair.area
            print(f"-- {area} " + "-" * (64 - len(area)))
        print(result)

    bad = [r for r in results if r.status == "FAIL"]
    info = [r for r in results if r.status == "INFO"]
    print()
    print(
        f"{len(results)} pairs checked, {len(bad)} failing, "
        f"{len(info)} recorded without assertion"
    )
    for result in bad:
        print(
            f"  FAIL  {result.pair.area}/{result.pair.label}: "
            f"{result.ratio:.2f} < {result.pair.requirement} "
            f"({result.pair.foreground} on {result.pair.background})"
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(_main())
