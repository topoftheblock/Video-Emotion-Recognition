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
"Accepted residual risk" at the end for what the second exclusion costs.

---

## Phase 0 — Baseline and tooling

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
saved, and the keyboard sweep is written down.

---

## Phase 1 — Keyboard access and accessible names

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

**1.6 — Keep the Ask submit button named while it spins.**
`css/ask.css:113-116` sets `color: transparent` on `:disabled` and spins a
pseudo-element. The visible text is the accessible name, so during the request
the button has no name at all.
- Swap the technique: keep `.btn-label` in the flow but hide it with the
  `.visually-hidden` utility from 1.2, or set an explicit `aria-label="Ask"` on
  the button so it survives the text going transparent.
- Add `aria-busy="true"` on the form or button while the request is in flight.
  `#askStatus` already has `role="status"` and announces "Thinking…", so this is
  reinforcement, not the primary signal.

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

**Done when:** the Phase 0.3 sweep reaches every control including Ask segment
results, every stop announces a name and a state, and axe reports no
name/role/value violations in all three captured states.

---

## Phase 2 — Document structure and navigation

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

**Done when:** the first Tab press reveals a working skip link, and a heading
outline (axe or a screen reader's heading list) shows a single `h1` with `h2`s
beneath it.

---

## Phase 3 — Contrast and colour independence

Four confirmed failures plus one judgement call. The token file already carries
a good contrast pass — this closes what it missed, mostly in places where a
colour is composited or computed at runtime rather than written literally.

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

**3.2 — Fix the selected person row's meta text.**
`css/sidebar.css:174` — `rgba(255,255,255,0.75)` over `--signal` composites to
`#bfdae5`, **3.99:1** at 12px.
- Raise the alpha to `0.85` (≈4.6:1) or use `--primary-100` literally.
- Verify against `--signal` only; `.person-row.is-selected:hover` shares the
  same background, so there is no second case.

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

**3.4 — Raise the signed-track centre marker.**
`css/emotions.css:119` draws the zero reference at `--border-strong`,
**2.35:1**. This is a meaningful reference line for valence/arousal/dominance,
not decoration — signed values are read relative to it.
- Move it to `--surface-400` (5.54:1). At 1px width the extra weight is not
  visually heavy.
- `--border` at 1.65:1 on panel edges and 1.48:1 on the topbar hairline is
  *fine* — purely decorative separation, explicitly exempt under 1.4.11. Do not
  change these; note the decision so it isn't re-raised.

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

**Done when:** the Phase 0.1 checker reports no pair below its threshold, the
`readableTextColor` test passes for the whole palette, and a CVD simulation
shows six distinguishable person colours.

---

## Phase 4 — Adaptive rendering modes

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
Same three application states, same keyboard sweep, diffed against the
baseline. Anything that regressed is a Phase 5 conflict and is cheapest to
find now.

**6.2 — Test with a real screen reader.**
Automated tooling cannot verify that the combobox's `aria-activedescendant`
actually announces, which is the whole point of 1.5. One pass with NVDA or
Orca over: picking a video, selecting a person, asking a question, and jumping
to a segment.

**6.3 — Wire the checks into CI.**
- The 3.1 palette contrast test and the 0.1 token checker belong in the
  existing `tests/` suite — they are pure functions over committed values and
  need no browser.
- Add axe-core to whatever runs the webapp tests, asserting zero violations on
  the three states.

**6.4 — Record the standing decisions.**
The panel-dot exemption (3.6), the decorative-border exemption (3.4), and the
two out-of-scope items below should be written into `css/tokens.css` and this
document, not left in a review thread. The token file's existing comments are
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
