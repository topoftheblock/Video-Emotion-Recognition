# Accessibility verification — after Phases 1–5

Phase 6.1 of [accessibility.md](accessibility.md). Run 2026-08-20
against the rebuilt container, diffed against
[a11y-baseline/](a11y-baseline/README.md), which is left untouched as the
before-picture.

Same method as the baseline: axe-core 4.10.2 injected into the live page at
`http://localhost:8010`, the same five application states, the same `fetch`
stub for the two Ask states (this stack still has no `DUUI_QUERY_API_KEY`), and
the same tab-order sweep. Desktop viewport, to match how the baseline was taken.

## The diff

| | baseline | now |
| --- | --- | --- |
| axe violations, all five states | 4 (2 critical) | **0** |
| — `aria-allowed-attr` (critical) | 1 node | gone |
| — `label` (critical) | 1 node | gone |
| — `page-has-heading-one` | 1 node | gone |
| — `region` | 2–3 nodes | gone |
| Contrast pairs failing | 25 of 82 | **0 of 79** |
| Palette pairs converging under CVD | 5 | **0** |
| Tab stops | 10 | 13 |
| Stops with no accessible name | 1 (`#scrub`) | **0** |
| Focusable elements in an Ask result | 0 | **3** |
| Heading outline | starts at `h2` | `h1` + 8×`h2` |

Nothing regressed. Every violation the baseline recorded is closed, and the
three findings Phase 0 added to the audit (`region`, the `person_1100%`
accessible name, the two extra contrast pairs) are closed with them.

## The tab order now

| # | Region | Element | Announced name | State |
| --- | --- | --- | --- | --- |
| 1 | page | `.skip-link` | Skip to player | – |
| 2 | header | `#videoComboInput` | Video | `expanded=false` |
| 3 | ask | `#askInput` | Ask a question about this video | – |
| 4 | ask | `#askSubmit` | Ask | `disabled=false` |
| 5 | ask | `#askReset` | Reset view | – |
| 6 | stage | `#playBtn` | Play | – |
| 7 | stage | `#subtitleToggle` | CC | `pressed=true` |
| 8 | stage | `#scrub` | Seek | `valuetext=0:00 of 3:27` |
| 9 | sidebar | `.person-legend-toggle` | What match confidence means | `expanded=false` |
| 10–12 | sidebar | `.person-row` ×3 | person_N match confidence NN% | `pressed=false` |
| 13 | sidebar | `.person-legend-toggle` | What match confidence means | `expanded=false` |

Names read through axe's own accessible-name implementation, not a
reimplementation of it.

## Incomplete results, and why they are expected

axe reports two rules as *incomplete* in every state. Neither is a finding, and
both should be expected on every future run:

- **`video-caption`** on `#player`. This is the out-of-scope
  subtitles-as-`<track>` item. It will not clear until that work is done.
- **`color-contrast`** on a long list of nodes, with `bgOverlap` or
  `pseudoContent` as the reason. Structural and older than any of this work:
  `.panel::before` draws each panel's accent bar, and `.panel-filter` and
  `.person-legend` are absolutely positioned, so axe declines to resolve those
  backgrounds at all. `contrast_check.py` covers every one of those pairs
  directly and they pass.

That second point is the baseline's main lesson, still true: axe's
`color-contrast` rule examined **nine** text nodes page-wide and passed them all
while the page was rendering a 2.18:1 chip. A clean axe run is necessary and
nowhere near sufficient — which is why the two static checkers exist.

## Static checkers

```text
contrast_check.py   79 pairs, 0 failing, 15 recorded without assertion
cvd_check.py        0 pairs below dE2000 10.0
pytest              11 passed
```

The 15 unasserted pairs are recorded decisions, not gaps — see
[the standing decisions](#standing-decisions) below.

## Responsive and font-size resilience

Twelve combinations, from Phase 5: 320 / 560 / 860 / 1280px, each at a 16px,
24px and 32px root font size. Zero horizontal overflow and zero clipped
elements in all twelve.

## Standing decisions

Recorded at their call sites so they are not re-litigated. Listed here as an
index only.

| Decision | Where the reasoning lives |
| --- | --- |
| Panel dots are decorative (labelled), exempt from 1.4.11 | `css/tokens.css`, accent block |
| `--border` hairlines are decorative separation, exempt | `css/tokens.css`, on `--border-input` |
| Emotion groove keeps 1.24:1 — value is printed as text beside it | `css/emotions.css`, `.emo-track` |
| Input fill no longer carries the boundary; its border does | `tests/support/contrast_check.py`, input pairs |
| Person swatch boundary is a ring, not the hue | `css/sidebar.css`, `tests/support/contrast_check.py` |
| `.person-swatch` opts out of forced colours; the hue *is* the data | `css/adaptive.css` |
| `.subtitle-box` opts out of forced colours; it sits over video | `css/adaptive.css` |
| Okabe-Ito palette, and why the grey separates by lightness | `js/state.js`, `tests/support/cvd_check.py` |
| The `19em` block that was tried and removed | `css/responsive.css`, end of file |

Each row above was checked against the file it names, not assumed. The
`--border` entry is the one that moved: it is recorded on `--border-input` in
`tokens.css`, which is where the contrast between the two is actually argued,
rather than in `emotions.css`.

## Still open

**A real screen-reader pass (6.2).** Not done, and not doable from this
environment — see the plan's 6.2 for exactly what to exercise. Everything above
verifies the accessibility *tree*; none of it verifies what a screen reader
actually announces from that tree, which is a different question and the only
way to confirm the combobox's `aria-activedescendant` behaves.

**Windows High Contrast (Phase 4).** Same limitation: the forced-colours rules
were verified as parsed-and-intact through the CSSOM, never seen rendered.
Worth doing in the same sitting as the screen-reader pass.
