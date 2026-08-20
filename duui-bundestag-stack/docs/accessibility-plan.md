# Frontend accessibility remediation plan

Scope: `duui-video-emotion-visualization-webapp/src/frontend`.

Ordering principle: **defects before refactors.** Phases 1–4 close findings that
block or degrade real use, each in a small, independently shippable diff.
Phase 5 is the one large mechanical change and lands once the defect list is
closed, so the refactor isn't rebased across a moving target. Phase 6 locks the
result in.

Two findings from the audit are deliberately **out of scope** and are not
planned here: converting the subtitle `<div>` to a real `<track>`/WebVTT
caption, and putting person names into the on-video bounding-box labels. See
"Accepted residual risk" at the end for what the second exclusion costs. The
first has a permanent signature in the tooling — axe reports `video-caption` as
*incomplete* against `#player` in every state — which Phase 6.1 must expect
rather than read as a regression.

Phase 0 is complete. The findings it added to the audit are folded into the
phases below and marked **found by Phase 0**.

---

## Phase 0 — Baseline and tooling

**Status: complete (2026-08-20).** Artefacts in
[a11y-baseline/](a11y-baseline/README.md). The checker is
`tests/contrast_check.py`; its gate is `tests/test_contrast.py`.

Cheap, and everything after it is measured against what this captures.

**0.1 — Add a contrast checker to the repo.**
Port the ad-hoc WCAG ratio script into `tests/` or `tools/` as a small Python
or Node module that reads the hex values out of `css/tokens.css` and
`js/state.js` and reports every pair the app actually composites. Alpha
compositing must be supported — several findings only appear once
`rgba()` is flattened against its real backdrop.

**0.2 — Capture the baseline.**
Run axe-core (or Lighthouse's a11y category) against the running app on a video
with: an active person filter, an Ask result containing segments, and an Ask
result containing a table. Save the report. These three states cover markup
that only exists after JS runs, which a static scan of `index.html` misses
entirely.

**0.3 — Record the manual keyboard sweep.**
Tab from page load to the end of the document and write down the order and
what each stop announces. This is the artefact Phase 1 is measured against;
without it "did we fix it" is a matter of opinion.

**Done when:** the checker runs from the repo, one axe report per state is
saved, and the keyboard sweep is written down. — done.

**What it changed about the rest of this plan.** Instrumenting the app found
four things that reading it did not, each folded into its phase below: an
unnamed `<section>` leaving the Ask panel outside every landmark (2.3), person
rows whose accessible name runs the name into the score (1.8), placeholder text
at 4.48:1 (3.3), and the emotion groove at 1.24:1 (3.4).

It also settled how progress is tracked. `tests/test_contrast.py` carries a
`KNOWN_FAILURES` baseline of all 25 currently-failing pairs, keyed by the phase
that clears each. It fails on a *new* failure and equally on a known one that
starts *passing*, so **striking an entry off that list is the last step of the
sub-task**, not an afterthought. Each Phase 3 sub-task names the entries it owns.

One caution the baseline established: axe found **none** of the contrast
failures and **none** of the keyboard failures. Its `color-contrast` rule
examined nine text nodes page-wide and passed them all while the page was
rendering a 2.18:1 chip; it cannot see a click handler on a bare `<li>` at all.
Do not read a clean axe run as evidence of anything beyond the rules it actually
evaluated.

---

## Phase 1 — Keyboard access and accessible names

**Status: complete.** Verified against the rebuilt container; results under
"Done when" below.

Highest severity, smallest diff, no dependencies on any other phase. One
finding here makes a headline feature mouse-only.

**1.1 — Make Ask segment results keyboard-operable.**
`js/panels/ask.js:50` builds `<li data-index>` and `:91` attaches a bare click
handler. No `tabindex`, no `role`, no key handling — the segment list cannot be
reached or activated without a pointer.
- Change the `<li>` content to a `<button type="button">` carrying
  `data-index`, exactly as `js/panels/people.js:60-70` already does for person
  rows. Keep the `<li>` as the list item.
- Move the click handler onto the button (`closest("[data-index]")`), which
  gets Enter and Space for free.
- Add `.ask-segment-list button` styles that reset the UA button chrome
  (`background:none; border:0; font:inherit; text-align:left; width:100%`) and
  a `:focus-visible` ring matching the one already used at `css/ask.css:112`.
- Do not add `tabindex` to the `<li>`. Use the existing button idiom rather
  than inventing a second one.

**1.2 — Give `#askInput` an accessible name.**
`index.html:49` has a placeholder and nothing else. Placeholders are not
accessible names and disappear on first keystroke.
- Add a `<label for="askInput">` — visually hidden is acceptable here since
  `.ask-title` already carries the visible heading — or `aria-label="Ask a
  question about this video"`.
- If going visually hidden, add a shared `.visually-hidden` utility to
  `css/base.css` now; Phase 2 needs it again for the skip link.

**1.3 — Give `#scrub` a name and a meaningful value.**
`index.html:97` is a bare `type="range"` with `min=0 max=1000`. A screen reader
announces "slider, 0" — no indication it seeks, and no indication of position.
- Add `aria-label="Seek"`.
- In `updateTransport()` (`js/player.js:47`), set `aria-valuetext` to the
  formatted clock alongside the existing `.value` write, so the announced value
  is "1:23 of 4:56" rather than a number out of 1000.
- Keep the `:active` guard — `aria-valuetext` must not be written while the
  user drags, for the same reason `.value` isn't.

**1.4 — Make the play button's label track its state.**
`index.html:91` is `aria-label="Play/Pause"` and never changes; only the icon
swaps in `js/player.js`.
- In the existing `play` and `pause` listeners, set `aria-label` to `"Pause"`
  and `"Play"` respectively, next to the `innerHTML` swap.
- The CC toggle's `syncToggleButton()` (`js/subtitles.js:57`) is the pattern to
  copy — consider factoring both into one small helper.

**1.5 — Repair the combobox ARIA.**
`index.html:22-26` puts `role="combobox"` and `aria-expanded` on the *input*,
but `js/videoLoader.js:141` and `:148` set `aria-expanded` on the *container*
(`el.videoSelect`). The input's value is stuck at `"false"` for the life of the
page. Separately, arrow-keying the list is entirely silent to assistive tech.
- Move both `setAttribute("aria-expanded", …)` calls onto `el.videoComboInput`.
- Give each option a stable id in `renderVideoOptions()`
  (`id="videoComboOpt-${v.video_id}"`).
- In `updateComboHighlight()`, set `aria-activedescendant` on the input to the
  highlighted option's id, and clear it in `closeCombo()`.
- Set `aria-selected="true"` on the highlighted option and `"false"` on the
  rest, in the same loop that toggles `.is-active`.
- Fix the `ArrowUp` branch: it currently floors at `0`, so it cannot return to
  "nothing highlighted". Either allow `-1` and clear `aria-activedescendant`, or
  wrap to the end of the list. Pick one and make `ArrowDown` symmetric.
- **Found by Phase 0:** axe reports `aria-toggle-field-name` as *incomplete*
  here because `<label class="video-picker">` (`index.html:19`) wraps the
  *entire* combobox — the input and the `role="listbox"` alike — so the label's
  text can be pulled into each option's accessible name. Unwrap it while the
  ARIA is open anyway: make it a sibling `<span>` the input points at, or drop
  it in favour of the `aria-label` the input already carries.

Confirmed live in the baseline: with the list open, `#videoSelect` reads
`aria-expanded="true"` while `#videoComboInput` — the element that actually has
`role="combobox"` — still reads `"false"`, and none of the ten options carries
an `id` or `aria-selected`.

**1.6 — Mark the Ask submit button busy while it spins.**

> **Correction.** The audit claimed this button loses its accessible name while
> disabled, because `css/ask.css:113-116` sets `color: transparent` and the
> visible text is the name. **That was wrong.** A name computed from contents
> depends on whether the element is *rendered*, not on what colour it is painted
> — `display: none` or `visibility: hidden` would remove it, `color: transparent`
> does not. Measured with axe's own accname implementation, the button announces
> "Ask" both enabled and disabled. The sub-task is kept, narrowed to the part
> that was real.

- Set `aria-busy="true"` on the button for the duration of the request and
  remove it in the `finally`. `#askStatus` is `role="status"` and announces
  "Thinking…", which is the actual notification; `aria-busy` makes the state
  discoverable by someone who navigates back to the control afterwards, rather
  than only at the instant the live region fires.
- Do **not** add a redundant `aria-label="Ask"`. It would duplicate a name the
  button already has, and would silently win over the visible text if that text
  ever changed — a worse failure than the one it was meant to fix.
- **Found while measuring, and fixed here too.** `disabled` took the button out
  of the tab order the instant it was set, so a keyboard user who had just
  pressed Enter or Space on it lost focus to the document body and had to tab in
  from the top of the page to reach the answer they had asked for. The button is
  `aria-disabled` now and keeps its place; a `pending` flag in the submit handler
  does the actual refusing, since the attribute enforces nothing by itself. The
  guard also covers Enter from inside the input, which submits the form without
  going near the button. `css/ask.css` keys the spinner off
  `[aria-disabled="true"]` instead of `:disabled`, so nothing about the look
  changed.

**1.7 — Make the match-confidence explanations reachable.**
`index.html:151` and `:173` put substantial explanatory text in `title` on a
non-focusable `<div>`. `title` is not reachable by keyboard, unreliable in
screen readers, and invisible on touch — and this is the only place the score's
meaning is written down.
- Convert each `.person-legend` into a `<button type="button">` with
  `aria-expanded` toggling a `<p>` that holds the text, so the explanation is a
  real disclosure rather than a hover affordance.
- Keep the `title` as well; it costs nothing and preserves the mouse behaviour.
- The same applies to the per-row `scoreTitle` in `js/panels/people.js:53-57`.
  That one is genuinely per-row and a disclosure per row would be noise —
  instead make sure the panel-level disclosure states the same thing, so the
  information is available somewhere non-hover.

**1.8 — Separate the person's name from their match score.** *(found by Phase 0)*
`js/panels/people.js:70` interpolates the score span immediately after the name
text with no whitespace between them:

```
${personName(p)}<span class="person-meta" title="${scoreTitle}">${score}</span>
```

The row is a `<button>`, so its accessible name is computed from its contents —
which concatenates to `person_1100%`. The keyboard sweep's stop 8 announces as
"person eleven hundred percent".
- A space in the template is the minimum fix. Better is to name the number,
  since "100%" on its own does not say what it measures.
- Preferred: give the score span an `aria-label` like `"match confidence 100%"`,
  or take it out of the button's name entirely with `aria-hidden` plus
  `aria-describedby`. Whichever is chosen has to agree with the wording 1.7
  settles on.
- `renderActiveList()` (`js/panels/people.js:88`) builds
  `${l.name}<span class="person-meta">${l.emotion}</span>` the same way and needs
  the same treatment.
- `js/panels/crossVideo.js:85-88` was checked and is **not** affected — its two
  spans sit on separate lines, so the template's newline already separates them.

**Done when:** the Phase 0.3 sweep reaches every control including Ask segment
results, every stop announces a name and a state distinct from the adjacent one,
and axe reports no name/role/value violations in any of the five captured
states — `aria-allowed-attr` and `label` both gone.

**Measured after the work, against the rebuilt container:**

| | before | after |
|---|---|---|
| axe `aria-allowed-attr` (critical) | 1 node | **gone** |
| axe `label` (critical) | 1 node | **gone** |
| axe `aria-toggle-field-name` (incomplete) | 1 node | **gone** |
| Focusable elements in a 2-segment Ask result | 0 | **2** |
| Tab stops, default state | 10 | 12 |
| Stops with no accessible name | 1 (`#scrub`) | **0** |
| Focus after activating Ask | lost to `<body>` | **stays on the button** |

Every stop's name, read through axe's accname implementation: "Video", "Ask a
question about this video", "Ask", "Reset view", "Play", "CC", "Seek"
(`valuetext="0:00 of 3:27"`), "What match confidence means", then
"person_1 match confidence 100%" and its two siblings, then the second legend.
Activating a segment row by its button seeks the player (12.5 → 31.2), and the
play button's name follows the media state (Play → Pause → Play).

The Ask button, checked live: focus stays on it through the request and after
it; it remains one of the 12 tab stops while in flight; and two further
activation attempts mid-request produced one network call, not three.

Combobox, checked live: `aria-expanded` now moves on the input and the wrapper
carries none; all ten options have ids; `aria-activedescendant` tracks the
highlight and clears on Escape; ArrowUp from the first option wraps to the last.

The only axe violations left in any state are `page-has-heading-one` and
`region` — both Phase 2 — and `video-caption`, which is out of scope. Note
`region` gained a node: the new visually-hidden `<label>` from 1.2 sits outside
a landmark like the rest of the Ask panel, and 2.3 clears it with the others.

One caveat on method: the real-`Tab` verification of the order could not be
repeated this round because the browser pane was not compositing, so the table
above is the computed focusable order. Phase 0 established that the computed and
observed orders match exactly on this page, which has no positive `tabindex`.

---

## Phase 2 — Document structure and navigation

**Status: complete.** Verified against the rebuilt container; results under
"Done when" below.

Small, but it changes how every screen-reader user enters the page, so it
belongs before the cosmetic work.

**2.1 — Add an `<h1>`.**
Headings currently start at `<h2>`; the page title is a `<span>`
(`index.html:17`). Heading navigation drops users into the middle of a
hierarchy with no document-level anchor.
- Promote `.topbar-title` to `<h1 class="topbar-title">`, or add a visually
  hidden `<h1>` naming the video being viewed.
- Prefer the visible promotion. `font-size: 16px; font-weight: 600` at
  `css/topbar.css:37` already overrides the UA `h1` styling, and `css/base.css`
  sets `h1…h6 { font-weight: bold }`, so confirm the weight still resolves to
  600 after the change.
- Audit the rest of the hierarchy while here: `.ask-title` and every
  `.panel-title` are `<h2>`, which is correct once an `<h1>` exists.

**2.2 — Add a skip link.**
There is no way past the sticky topbar and the whole Ask panel to reach the
player.
- First child of `<body>`: `<a class="skip-link" href="#stageFrame">Skip to
  player</a>`.
- Style it off-screen by default and visible on `:focus` — reuse the
  `.visually-hidden` utility from 1.2 with a `:focus`/`:focus-within` escape.
- Give `#stageFrame` `tabindex="-1"` so the jump actually moves focus rather
  than only scrolling.
- Ensure its `z-index` clears the topbar's `20` (`css/topbar.css:17`) and the
  combobox list's `30` (`css/topbar.css:~93`).

**2.3 — Make the Ask panel a real landmark.** *(found by Phase 0)*
axe reports `region` in every captured state: `.ask-panel` (`index.html:36`) is
a bare `<section>`, and an unnamed `section` is not a landmark, so
`.ask-heading`, `#askInput` and `#askResults` all sit outside every landmark on
the page. Landmark navigation skips the entire feature.
- Name it: `aria-labelledby` on the `<section>` pointing at `.ask-title`
  (`index.html:44`), which needs an `id`. That promotes it to a `region`
  landmark and clears all three nodes at once.
- Do this after 2.1, so the heading it points at is already settled.
- Verify in the Ask-results state, not just on load: the violation lists two
  nodes at rest and three once results are rendered.

**Done when:** the first Tab press reveals a working skip link, a heading
outline (axe or a screen reader's heading list) shows a single `h1` with `h2`s
beneath it, and axe's `region` violation is gone in both the default and the
Ask-results state.

**Measured after the work, against the rebuilt container:**

| | before | after |
|---|---|---|
| axe violations, all five states | 2 (`page-has-heading-one`, `region`) | **0** |
| `region` nodes, Ask-results state | 6 | **0** |
| Heading outline | starts at `h2` | **one `h1`, then `h2`s** |
| First tab stop | the video combobox | **the skip link** |
| Tab stops, default state | 12 | 13 |

axe now reports **zero violations in every captured state** — default, person
filter, Ask segments, Ask table, combobox open. The heading outline is one `h1`
("Emotion Visualization") followed by eight `h2`s.

Promoting `.topbar-title` to `<h1>` needed three resets, not none: the UA's
`0.67em` block margin would have pushed the topbar around, and its font family
and size both had to be restated. Checked after the change — the topbar is the
same 65px tall and the title still renders at 16px/600 in Oxanium.

The skip link is the first child of `<body>`, measures 1×1 while clipped, and
expands to a 124×40 control at (8,8) that hit-tests **above** the sticky topbar,
so `z-index: 40` clears both the bar (20) and the combobox dropdown (30).
Following it moves focus to `#stageFrame`, not just the scroll position.

Two notes on method, both environmental rather than defects:

- The browser pane was backgrounded for this round (`document.hasFocus()` is
  `false`, `visibilityState` is `"hidden"`), so `:focus` cannot match and real
  `Tab` presses do not reach the page. The skip link's focused geometry was
  therefore verified by applying the `:focus` rule's declarations directly and
  measuring those; the only unverified link is the one-line `:focus` trigger.
  The tab order above is the computed focusable order, which Phase 0 established
  matches the observed one on this page.
- State E (combobox open) reports `color-contrast` as *incomplete* on
  `.btn-label` and `#askReset`. That is the open dropdown overlapping them —
  axe will not judge contrast for an element it cannot see the background of. It
  is an artefact of the state, not a finding, and Phase 6.1 should expect it.

---

## Phase 3 — Contrast and colour independence

**Status: complete.** Verified against the rebuilt container; results under
"Done when" below.

**25 failing pairs** of the 82 the Phase 0 checker measures: the audit's four
findings, expanded per-colour across the person palette, plus two the checker
found on its own. The token file already carries a good contrast pass — this
closes what it missed, which is almost entirely where a colour is composited or
computed at runtime rather than written literally, and so was invisible to a
reading of the stylesheets.

Every sub-task below owns a set of `KNOWN_FAILURES` entries in
`tests/test_contrast.py` and names them. Deleting those entries is the last step
of the sub-task; the suite fails if a fixed pair is left in the list, so the
ledger cannot drift out of date.

### Text contrast (needs 4.5:1)

**3.1 — Fix `readableTextColor()`'s threshold.**
`js/state.js:74` picks dark-vs-white text by `L > 0.45`. The real crossover for
`#0b0e14`/`#ffffff` is near `L ≈ 0.18`, so four of the seven person colours get
white text at **2.18–3.06:1** on `.panel-filter`
(`js/panels/emotions.js:134`) whenever that person is the active filter:

| colour | current | picks | correct choice |
|---|---|---|---|
| `#e0a458` | 2.18:1 | white | dark → 8.97:1 |
| `#c77dff` | 2.69:1 | white | dark → 7.28:1 |
| `#f472b6` | 2.65:1 | white | dark → 7.39:1 |
| `#8b94a3` | 3.06:1 | white | dark → 6.40:1 |

- Replace the luminance threshold with a real comparison: compute the contrast
  ratio of the candidate dark and the candidate white against `hex`, return
  whichever is higher. That is threshold-free and stays correct if the palette
  changes in 3.5.
- Add a unit test asserting ≥4.5:1 for every entry in `PERSON_COLORS` plus
  `UNKNOWN_PERSON_COLOR`. This is the check that would have caught it.
- While here: `js/overlay.js:107-109` hardcodes `#0a0c0f` for the on-video
  emotion tag instead of calling `readableTextColor()`. It happens to pass
  (6.40–12.99:1 across the palette) but it is a second, independent copy of the
  same decision. Route it through the fixed function.
- Clears `KNOWN_FAILURES`: the four `person/filter chip text on …` entries.

**3.2 — Fix the selected person row's meta text.**
`css/sidebar.css:174` — `rgba(255,255,255,0.75)` over `--signal` composites to
`#bfdae5`, **3.99:1** at 12px.
- Raise the alpha to `0.85` (≈4.6:1) or use `--primary-100` literally.
- Verify against `--signal` only; `.person-row.is-selected:hover` shares the
  same background, so there is no second case.
- Clears `KNOWN_FAILURES`: `sidebar/score on selected row`.

### Non-text contrast (WCAG 1.4.11, needs 3:1)

**3.3 — Give text inputs a visible boundary.**
`--border-soft` is **1.31:1** on white, and the `--surface-alt` fill is
**1.24:1** against the white card. Neither cue identifies the Ask input
(`css/ask.css:73`) or the video combobox (`css/topbar.css:61`) as a field until
it is focused.
- Introduce a `--border-input` token at ≥3:1 against both `--surface` and
  `--surface-alt`. `--surface-300` (#a7a9ae, 2.35:1) is not enough;
  `--surface-400` (#666872, 5.54:1) clears it with room.
- Apply to `.ask-input` and `.video-combobox-input` at rest. Leave the focus
  treatment alone — the 2px `--signal` ring at `css/ask.css:86` and
  `css/topbar.css:79` is already correct.
- Check the same token against `.video-combobox-list` (`css/topbar.css:~97`),
  which uses `--border-soft` for a popup edge over page content.
- **Found by Phase 0:** placeholder text is `--text-dim` on the recessed
  `--surface-alt` fill, which is **4.48:1** — under AA by a hair. The audit
  measured `--text-dim` on the card (5.54:1) and on the page floor (4.95:1), but
  not on the fill placeholders actually sit on. Cheapest fixed here, since this
  sub-task already opens both inputs: darken `--text-dim` slightly, or give the
  placeholder its own token. Note this one is a *text* threshold (4.5:1), not the
  3:1 the rest of this sub-task is about.
- Clears `KNOWN_FAILURES`: `input/resting border vs card`,
  `input/resting border vs own fill`, `input/input fill vs card`,
  `input/dropdown border vs card`, `input/placeholder on input fill`.

**3.4 — Give the emotion tracks perceivable geometry.**
`css/emotions.css:119` draws the signed tracks' zero reference at
`--border-strong`. The audit measured that against the card and got 2.35:1; its
real backdrop is the groove fill, where it is **1.90:1**. This is a meaningful
reference line for valence/arousal/dominance, not decoration — signed values are
read relative to it.
- Move it to `--surface-400` (4.48:1 on the groove). At 1px width the extra
  weight is not visually heavy.
- **Found by Phase 0:** the groove itself (`--surface-alt`) is **1.24:1** against
  the card, so the track's *extent* — the thing a fill is read as a proportion
  of — has no perceivable boundary. Decide this explicitly: either give
  `.emo-track` a 1px edge in the `--border-input` token from 3.3, or record a
  reasoned exemption on the grounds that the fill's own 4.72:1 against the groove
  is enough to read a magnitude from. Do not leave it undecided — it is the same
  token pair as `input fill vs card`, which 3.3 *is* fixing, so an unexplained
  split between the two will read as an oversight.
- `--border` at 1.65:1 on panel edges and 1.48:1 on the topbar hairline is
  *fine* — purely decorative separation, explicitly exempt under 1.4.11. Do not
  change these; note the decision so it isn't re-raised.
- Clears `KNOWN_FAILURES`: `emotions/signed zero marker vs groove`. For
  `emotions/groove vs card`, either the new edge clears it, or the exemption is
  recorded by moving that pair to `INFO` in `contrast_check.py` — the same
  treatment the panel dots get in 3.6 — and dropping it from the baseline. Either
  way the entry leaves the list.

**3.5 — Give person swatches a contrasting boundary.**
Swatches sit at **1.35–2.73:1** against the `--surface-50` row fill, and they
are the only link between a sidebar name and an on-video box.
- Do **not** darken the palette. These same colours are stroked over arbitrary
  video footage in `js/overlay.js:95`, where they need to stay bright. The two
  surfaces pull in opposite directions.
- Instead give `.person-swatch` a hairline ring — `box-shadow: 0 0 0 1px
  var(--surface-400)` or an equivalent border — which carries the 3:1 boundary
  without touching hue. Apply to `.cross-list .person-swatch` too
  (`css/sidebar.css:234`).
- Check the ring does not break the `is-selected` row, where the backdrop is
  `--signal` rather than `--surface-50`.
- Clears `KNOWN_FAILURES`: all thirteen `person/swatch …` entries. The checker
  measures every colour against both the row fill and the card, because
  `.active-list` rows have no fill of their own — the ring has to clear 3:1 on
  both.

**3.6 — Decide on the panel dots, and write the decision down.**
`--accent-people` (#00bcff) is **2.18:1** on white. Every dot is adjacent to a
text label naming the same panel, so colour is not the sole channel and this
passes as decoration.
- Recommendation: leave the hues alone, and record in `css/tokens.css` that the
  dots are decorative-with-adjacent-label. The token comments already document
  the reasoning behind the accent spacing; this is one more line in the same
  place.
- If the dots ever become the sole distinguisher, this decision must be revisited.

**3.7 — Check the palette for colour-vision deficiency.**
Because the in-frame name label is out of scope, hue is the *only* channel
mapping a bounding box to a sidebar entry. That makes the palette's CVD
separability load-bearing.
- Run `PERSON_COLORS` (`js/state.js:9-19`) through a deuteranopia/protanopia/
  tritanopia simulation. The pairs to scrutinise are `#a3e635`/`#e0a458` and
  `#f472b6`/`#8b94a3`.
- Where two colours converge, replace one, keeping brightness high enough for
  video overlay use.
- Re-run the 3.1 unit test afterwards — any palette change must preserve the
  ≥4.5:1 chip guarantee.

**What the simulation actually found, and what was done.** Five convergent
pairs, not the two this sub-task predicted: `#a3e635`/`#e0a458` and
`#f472b6`/`#8b94a3` as expected, plus `#49d3c8`/`#7dd3fc` under tritanopia
(dE2000 **4.31**), `#49d3c8`/`#f472b6` under deuteranopia (**5.26**), and
`#f472b6`/`#8b94a3` under protanopia too. Five of the seven entries were
involved, so replacing "one" was not on the table.

The palette is now **Okabe-Ito**, the standard colour-vision-safe qualitative
set, whose six hold a worst case of **11.13**. This is a visible design change:
the app moves from pastels to Okabe-Ito's more saturated tones.

The unknown-person grey needed separate thought. Every established palette
tested — Okabe-Ito, Tol bright, Tol light, Tol muted — passed among its own
colours and failed *only* against the old `#8b94a3`, which sat in the middle of
the lightness band where deficiency-collapsed hues land (2.58 from Okabe-Ito's
mauve). Deficiency leaves lightness essentially intact, so the fallback is now
separated on that axis instead: `#c8c8d0`, clearing every entry by **13.68**.
`tests/cvd_check.py` and `tests/test_palette.py` are the guard.

**Done when:** `KNOWN_FAILURES` in `tests/test_contrast.py` is empty and the two
tests that read it have been replaced by a direct
`assert contrast_check.failures() == []`, the `readableTextColor` test passes for
the whole palette, and a CVD simulation shows six distinguishable person
colours.

**Measured after the work, against the rebuilt container:**

| | before | after |
|---|---|---|
| Failing contrast pairs | 25 of 82 | **0 of 79** |
| `KNOWN_FAILURES` entries | 25 | **0** — baseline deleted |
| Filter chip, worst person colour | 2.18:1 | **5.00:1** |
| Convergent palette pairs under CVD | 5 | **0** |
| Worst palette separation | dE2000 4.31 | **11.13** |
| axe violations, all states | 0 | **0** |

Six pairs are now recorded as `INFO` rather than asserted, each argued at its
call site: the four panel dots and the two `--border` hairlines (decorative,
labelled), the emotion groove (3.4), and the input fill (its boundary moved to
the border). Seven more record the raw swatch-on-surface ratios, which the ring
in 3.5 exists to compensate for.

**3.4's open question was decided as an exemption, not an edge.** The groove
keeps its 1.24:1 against the card. The reasoning, written into
`css/emotions.css`: every row prints its live value *and* its average as text in
the two columns beside the bar, so the track is a second reading of a number
already on screen rather than a graphic required to understand anything. That is
a different situation from the text inputs in 3.3, where the boundary is the
only thing announcing a control exists — which is the explanation the plan asked
for so the split would not read as an oversight.

Two things worth carrying forward:

- The checker duplicates one literal it cannot read — the `0.85` alpha in
  `.person-row.is-selected .person-meta`. Changing the stylesheet without the
  registry silently re-opens the pair; the comment there says so.
- axe's `color-contrast` now reports a long list of *incomplete* nodes in the
  populated states (`bgOverlap` and `pseudoContent`). These are structural and
  predate this phase — `.panel::before` draws the accent bar, and
  `.panel-filter` and `.person-legend` are absolutely positioned — so axe
  declines to resolve those backgrounds at all. `contrast_check.py` covers every
  one of those pairs directly and they pass. It is the Phase 0 lesson again:
  a clean axe run is not the measurement.

---

## Phase 4 — Adaptive rendering modes

**Status: complete.** Verified against the rebuilt container; results under
"Done when" below.

Depends on Phase 3: these modes need the final token values to key off.

**4.1 — Declare the colour scheme.**
`css/tokens.css` is explicitly light-only, but nothing tells the browser. UA
widgets — the `type="range"` scrubber, the text inputs, scrollbars — may render
with dark-mode chrome against light fills on a system set to dark.
- Add `color-scheme: light` to `:root` in `css/base.css`.
- This is the honest minimum. Actual dark-mode support is a separate project
  and is not in this plan.

**4.2 — Support forced-colors / Windows High Contrast.**
With forced colours on, backgrounds are stripped — which removes the emotion
track fills (`css/emotions.css:126`), the average markers (`:137`), and the
person swatches. The data disappears while the layout survives.
- `.emo-fill`, `.emo-avg-mark`, `.emo-track` and `.person-swatch` carry meaning
  in their backgrounds. Give them `forced-color-adjust: none` inside a
  `@media (forced-colors: active)` block, or re-express them with system
  colours (`Highlight`, `CanvasText`).
- Add explicit borders to `.emo-track` and `.person-swatch` in that block so
  they retain a shape even where the fill is overridden.
- Verify the focus rings survive — `outline` is generally preserved, but the
  `box-shadow` rings on the two inputs (3.3) are not, so those need an
  `outline` fallback under forced colours.
- The `<canvas>` overlay is unaffected by forced colours and needs nothing.

**4.3 — Honour `prefers-contrast: more`.**
Nothing currently responds to it.
- Add a `@media (prefers-contrast: more)` block re-pointing the handful of
  tokens that sit closest to their floor: `--text-dim` → `--surface-500`,
  `--border` → `--surface-300`, `--border-input` → `--surface-500`.
- Keep it to token overrides. If it needs per-rule changes, the token layer is
  in the wrong shape and that should be fixed instead.
- `prefers-reduced-motion` at `css/responsive.css:124` is already handled
  correctly — nothing to do.

**Done when:** the app is legible and complete with Windows High Contrast
active, and `prefers-contrast: more` visibly raises the dim text.

**How it landed.** All three modes live in a new `css/adaptive.css`, imported
last so its overrides win. `prefers-reduced-motion` moved there out of
`responsive.css`, which is now purely about viewport width — the three
preference queries had no reason to be split across two files.

`prefers-contrast: more` is four token overrides and no per-rule changes, which
was the test of whether the token layer is in the right shape. Measured:

| pair | default | more contrast |
|---|---|---|
| `--text-dim` on the card | 5.54 | **14.82** |
| `--text-dim` on the page floor | 4.95 | **13.24** |
| placeholder on the input fill | 5.22 | **11.99** |
| `--border-input` on the card | 5.54 | **14.82** |
| `--border-input` on its own fill | 4.48 | **11.99** |

Forced colours came to 14 rules. Two of them are the ones worth naming:

- **The two text inputs would have had no focus indicator at all.** Both
  suppress `outline` and draw a `box-shadow` ring instead (Phase 3.3's
  neighbours), and box shadows are dropped in forced-colours mode — a
  regression invisible until someone tries to use the app that way.
- **The combobox's highlighted option**, found while reviewing the rule list
  rather than from the plan. It is keyboard state — the only thing saying which
  row ArrowDown has landed on — and it was carried entirely by a background
  fill, which is exactly what forced colours strips.

`.person-swatch` is the one element given `forced-color-adjust: none`, because
there its specific colour *is* the information: it ties a name in the sidebar to
a stroked box on the video, and the video is a `<canvas>`, which forced colours
does not touch. Substituting a system colour would break that match while
looking perfectly fine. It takes a real `border` in the same block, since the
ring that normally supplies its boundary is a box-shadow. `.subtitle-box` opts
out for a different reason: it sits over video, so a system `Canvas` fill would
paint an opaque block across the picture.

**A caveat on verification.** This environment cannot toggle forced colours or
`prefers-contrast`, so none of the above was seen rendered. What was checked is
that every rule *parsed with its declarations intact* — read back through the
CSSOM, where a mistyped system-colour keyword would have been dropped silently
and shown up as an empty declaration. All 14 survived. The contrast figures come
from `contrast_check.py` over the overridden token values. Phase 6.2's screen
reader pass is the natural place to also put the app in front of real Windows
High Contrast, and until then this phase is verified by construction rather than
by observation.

---

## Phase 5 — Typography scale (px → rem)

The one large mechanical change: 48 `font-size` declarations across 8 files.
Deliberately last among the code phases — it touches nearly every stylesheet,
so running it while Phases 1–4 are in flight guarantees conflicts.

**5.1 — Define the scale in `css/tokens.css`.**
Sizes are currently written literally at call sites, with `14px` appearing 15
times and `12px` 12 times and nothing tying them together. Converting without
centralising is 48 independent edits with nothing preventing drift afterwards.

```
--text-2xs:  0.625rem   /* 10px */
--text-xs:   0.75rem    /* 12px */
--text-sm:   0.875rem   /* 14px */
--text-base: 1rem       /* 16px */
--text-lg:   1.125rem   /* 18px */
--text-xl:   1.3125rem  /* 21px */
```

Place it in the semantic-aliases half of the file, matching the existing
two-layer structure.

**5.2 — Resolve the two off-scale values first.**
`12.5px` (`css/ask.css:60`, `.ask-subtitle`) and `13px` (`css/stage.css:210`,
`.transport-toggle`) do not land on the scale. Decide before converting:
normalise each onto the nearest step, or add a token for it. Do not carry
`0.78125rem` into the new system.

**5.3 — Convert file by file, smallest first.**
`jobs.css` (2) → `responsive.css` (3) → `emotions.css` (6) → `topbar.css` (6) →
`stage.css` (7) → `sidebar.css` (10) → `ask.css` (12). One commit per file
keeps each reviewable and each revert cheap.
- Convert `font-size` only. Leave `px` on borders, radii, and genuinely fixed
  layout dimensions such as `.emo-track { height: 6px }`.
- `css/sidebar.css:262` is `font-size: inherit` — leave it.
- The `clamp()` values need both bounds converted, not just one:
  `css/stage.css:74`, `:125`, `:139` and `css/responsive.css:111`, `:112`.
  Leave the `vw` middle terms untouched.

**5.4 — Re-check the layout comments that assume pixel sizes.**
`css/responsive.css` reasons in exact pixels in several places — the 64px
`.emo-row` label floor is derived from "Ubuntu Mono's 0.5em advance at 14px",
and the transport wrap threshold from a 129px intrinsic range-input minimum.
Once font size scales with the user's preference, those derivations hold at
the default and break above it.
- Re-verify the ≤560px emotion row and the transport wrap at 100%, 150% and
  200% browser font size.
- Update the comments to state the assumption explicitly rather than quoting a
  pixel figure as though it were fixed.

**5.5 — Fix the canvas label font.**
`js/overlay.js:100` sets `600 12px 'IBM Plex Mono', monospace`. Two problems:
IBM Plex Mono **is not a font this app ships** — the self-hosted mono is Ubuntu
Mono — so that label has always rendered in the generic fallback; and canvas
text is absolutely sized, so it cannot scale at all.
- Change the family to `'Ubuntu Mono', monospace` to match the rest of the app.
- Derive the size from the root font size at draw time rather than hardcoding:
  read `parseFloat(getComputedStyle(document.documentElement).fontSize)` and
  scale from it, so the overlay label tracks the user's preference like
  everything else.
- The label's box geometry is computed from `measureText()` and the literal
  `16`/`18`/`12` offsets around `js/overlay.js:104-110`. Those must be derived
  from the same size, not left as constants, or the box and the text will
  separate as soon as the size changes.

**Done when:** the app is fully usable with the browser's default font size set
to its largest setting, at 320px, 560px, 860px and desktop widths, with no
clipping or horizontal scroll.

---

## Phase 6 — Verification and regression guard

**6.1 — Re-run the full Phase 0 battery.**
The same five application states and the same keyboard sweep, diffed against
[a11y-baseline/](a11y-baseline/README.md). Anything that regressed is a Phase 5
conflict and is cheapest to find now.
- Expect `video-caption` to still be reported *incomplete* against `#player`.
  That is the out-of-scope subtitles finding, not a regression.
- Expect `color-contrast` *incomplete* on many nodes once the panels are
  populated — `bgOverlap` where the dropdown or an absolutely-positioned chip
  covers something, `pseudoContent` wherever `.panel::before` draws the accent
  bar. axe will not judge contrast through either. Not a regression;
  `contrast_check.py` is what actually covers those pairs.
- The sweep should now show a skip link at stop 1, three new stops for the Ask
  segment list, a named slider, a play button whose label tracks its state, and
  person rows whose name and score do not run together.
- Reaching the two Ask states still needs the `fetch` stub documented in the
  baseline, unless `DUUI_QUERY_API_KEY` is configured by then.

**6.2 — Test with a real screen reader.**
Automated tooling cannot verify that the combobox's `aria-activedescendant`
actually announces, which is the whole point of 1.5. One pass with NVDA or
Orca over: picking a video, selecting a person, asking a question, and jumping
to a segment.

**6.3 — Wire the checks into CI.**
- `tests/contrast_check.py` and `tests/test_contrast.py` already sit in the
  webapp suite and need no browser, no database and no third-party package
  beyond pytest itself. Nothing more is required than including them in whatever
  already runs `pytest`.
- Once Phase 3 empties `KNOWN_FAILURES`, collapse the two baseline tests into a
  direct `assert contrast_check.failures() == []`, so a later palette change
  cannot quietly re-open a fixed pair by re-adding itself to the list.
- Add axe-core to whatever runs the webapp tests, asserting zero violations on
  the five states. That needs the stack up and a headless browser, so it belongs
  in a separate job from the pure-function tests rather than gating them.

**6.4 — Record the standing decisions.**
The panel-dot exemption (3.6), the decorative-border exemption (3.4), whatever
3.4 decides about the emotion groove, and the two out-of-scope items below should
be written into `css/tokens.css`, `tests/contrast_check.py` and this document,
not left in a review thread. The token file's existing comments are
the right precedent — the reasoning is already documented there, and this keeps
the next person from re-litigating settled calls.

---

## Accepted residual risk

Excluding the in-frame name label leaves one finding open. On the video, a
bounding box is identified **only** by hue; the mapping to a name exists solely
in the sidebar swatch. For a user who cannot distinguish two palette entries,
there is no second channel to fall back on — this is a WCAG 1.4.1 gap that
Phase 3.7 mitigates but does not close.

Phase 3.7 is therefore doing more work than it would otherwise: with no
redundant text channel, palette separability under CVD is the only defence, so
that step should not be treated as optional polish.
