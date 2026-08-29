# Frontend accessibility

How the webapp's frontend stays accessible, and what to do so that it keeps
staying that way.

This was a remediation plan once. The work is done — the phase-by-phase plan,
its findings and its measurements are in git history and in
[a11y-verification.md](a11y-verification.md), which records the before/after
numbers against [a11y-baseline/](a11y-baseline/README.md). This file is what
replaced it: the rules to work by, and an honest list of what is still missing.

Paths below are relative to the webapp project root
(`webapp/`), except `css/…` and `js/…`, which
are relative to `src/frontend/`.

---

## Checking your work

Two halves. The first needs nothing but pytest — no browser, no database, no
application dependencies — which is what makes it cheap enough to run on every
change:

```bash
docker run --rm -v "$PWD":/w -w /w python:3.14-slim sh -c \
  "pip install -q pytest && pytest tests/test_contrast.py tests/test_palette.py \
   tests/test_markup.py tests/test_stylesheets.py tests/test_scripts.py -q"
```

For the colour reports rather than pass/fail:

```bash
docker run --rm -v "$PWD":/w -w /w python:3.14-slim python3 tests/support/contrast_check.py
docker run --rm -v "$PWD":/w -w /w python:3.14-slim python3 tests/support/cvd_check.py
```

The second half needs the app running, because three of the five states it
checks only exist after JavaScript has run:

```bash
docker compose up -d pgvector-db webapp     # from the stack root
```

then open `http://localhost:8010`, paste `tests/a11y_browser_check.js` into the
console and run `await a11yCheck()`. Compare against
[a11y-verification.md](a11y-verification.md).

**What the automated half does not cover:** anything CSS decides at runtime,
anything JavaScript renders, and — most importantly — what a screen reader
actually announces. A clean run is necessary and nowhere near sufficient. The
baseline measured axe's `color-contrast` rule examining **nine** text nodes
page-wide and passing them all while the page was rendering a 2.18:1 chip.

---

## Guidelines

Each rule says what enforces it. Rules marked **judgement** have no automated
backstop and depend on whoever is reviewing.

### Structure and markup

- **Interactive things are `<button>`, `<a>` or `<input>`.** Never a click
  handler on a `<div>` or `<li>`. Those are unreachable by keyboard, and no
  automated tool can see the problem — a click listener leaves no trace in the
  accessibility tree. This is how the Ask results were mouse-only.
  → *judgement*, partially caught by `a11y_browser_check.js`
- **Never a positive `tabindex`.** It pulls an element out of document order and
  forces every other control to be reasoned about relative to it.
  → `test_markup.py::test_no_positive_tabindex`
- **Visual order must match DOM order.** To move something, change the layout
  (`flex-basis`, wrapping, grid placement) — never `order` or `row-reverse`.
  Reordering visually while leaving the DOM alone looks identical and makes a
  keyboard user tab through the page in a sequence that does not match what they
  can see. → *judgement*
- **One `<h1>`, and no skipped heading levels.**
  → `test_exactly_one_h1`, `test_heading_levels_do_not_skip`
- **Every focusable element sits inside a landmark.** An unnamed `<section>` is
  *not* a landmark — give it `aria-labelledby` pointing at its heading. The skip
  link is the one legitimate exception.
  → `test_every_focusable_element_is_inside_a_landmark`
- **The skip link stays first** and its target keeps `tabindex="-1"`, or
  following it moves the scroll position without moving focus.
  → `test_skip_link_is_the_first_focusable_element`, `test_skip_link_targets_a_real_and_focusable_element`
- **ids are unique and every reference resolves.** A dangling `aria-controls` is
  worse than none: it removes the relationship silently.
  → `test_ids_are_unique`, `test_every_id_reference_resolves`
- **The document declares its language.** Note this covers the document only —
  marking foreign-language *parts* is an open gap, see below.
  → `test_html_declares_a_language`

### Names

- **Every control has an accessible name.** Not a placeholder (it disappears on
  the first keystroke) and not a `title` (unreachable by keyboard, unreliable in
  screen readers, invisible on touch). `title` is fine *alongside* a name.
  → `test_every_focusable_element_has_an_accessible_name`,
  `test_no_control_is_named_only_by_its_placeholder`,
  `test_no_control_is_named_only_by_its_title`
- **A name that describes state must change when the state does.** `"Play/Pause"`
  announces both and is never accurate about either. Move the icon and the name
  together in one function — `syncPlayButton()` in `js/playback/player.js` and
  `syncToggleButton()` in `js/playback/subtitles.js` are the pattern.
  → *judgement*, with
  the initial value checked by `test_toggle_buttons_declare_their_pressed_state`
- **Interpolating a value next to a name needs a separator, and the value needs
  naming.** `${name}<span>${score}</span>` with no whitespace concatenates into
  `person_1100%` — "person eleven hundred percent". Put a separator between them
  *and* give the value an `aria-label` saying what it measures; `100%` alone
  names no quantity.
  → `test_scripts.py::test_person_rows_separate_the_name_from_the_metadata`
- **Information must never live only in a `title`.** If it is worth writing, it
  is worth reaching — make it a disclosure. → *judgement*

### Keyboard and state

- **ARIA state goes on the element that carries the role.** `aria-expanded` on a
  bare `<div>` is invalid markup *and* leaves the real combobox permanently
  reading "collapsed".
  → `test_combobox_state_lives_on_the_element_that_has_the_role`
- **A composite widget needs all of it**: stable `id`s on the options,
  `aria-activedescendant` on the input tracking the highlight, `aria-selected` on
  the options, and the reference cleared when the list closes. Without the ids,
  arrowing through the list is silent. → `a11y_browser_check.js`
- **Do not use `disabled` to mean "busy".** It removes the control from the tab
  order the instant it is set, so a keyboard user who just activated it loses
  focus to the document body. Use `aria-disabled` plus a guard in the handler
  that actually refuses the action — the attribute enforces nothing on its own,
  and the guard must also cover Enter-in-the-input, which submits a form without
  touching the button. → *judgement*
- **A visible focus indicator on everything.** If you suppress `outline`, you owe
  a forced-colours fallback (see below).
  → `test_stylesheets.py::test_suppressed_outlines_have_a_forced_colours_fallback`
- **Disclosures start closed and say so**: `aria-expanded="false"` with the panel
  `hidden`. → `test_disclosure_buttons_are_wired_both_ways`

### Colour and contrast

- **Colours come from tokens in `css/tokens.css`.** An undefined `var(--typo)`
  does not error; it drops the declaration silently.
  → `test_every_custom_property_used_is_defined`
- **Adding a colour combination means adding it to the registry.** The pair list
  in `tests/support/contrast_check.py` is curated, not discovered — there
  is no way to know from a stylesheet which colours end up stacked on
  which. A combination that is not in the registry is not checked.
  → *judgement*, then `test_contrast.py::test_no_contrast_failures`
- **Thresholds:** 4.5:1 for text, 3:1 for large text and for anything non-text
  that conveys meaning or marks a control's boundary. Exemptions are allowed but
  must be written down at the call site and recorded as `INFO` in the registry.
- **Never darken the person palette to fix sidebar contrast.** Those same colours
  are stroked over arbitrary video, where they must stay bright. The swatch's
  boundary comes from its ring, not its hue.
- **Changing the person palette means re-running `cvd_check.py`.** Hue is the
  only thing linking a box on the video to a name in the sidebar, so two colours
  that collapse under a deficiency make two people indistinguishable with no text
  fallback. → `test_palette.py`
- **Do not rely on hue alone** for anything else. Every panel dot is exempt from
  the 3:1 rule *only* because it sits beside a text label saying the same thing.
- **Text colour chosen at runtime goes through `readableTextColor()`**, which
  compares both candidates rather than thresholding on luminance. The threshold
  it replaced sat far above the true crossover and handed white text to four of
  seven person colours at 2.2–3.1:1.
  → `test_readable_text_color_clears_aa_for_every_person_colour`

### Type and layout

- **The scale itself lives in `css/tokens.css` and is expressed in `rem`.**
  → `test_scale_tokens_exist_and_are_relative`
- **`font-size` only ever comes from the scale, in `rem`.** A `px` font-size
  ignores the browser's own font-size setting — the control a low-vision reader
  actually reaches for, and the one that does not reflow the layout the way page
  zoom does.
  → `test_no_font_size_is_written_in_px`, `test_every_font_size_comes_from_the_scale`
- **Nothing sets `font-size` on `:root` or `html`.** Every `rem` is relative to
  it; setting it rescales the interface and defeats the reader's own setting.
  → `test_nothing_sets_a_font_size_on_the_root`
- **A dimension derived from text is expressed in `em`, not `px`.** The emotion
  row's label column is nine characters at Ubuntu Mono's 0.5em advance — that is
  `4.5em`, not the 63px it happens to equal at a 16px root. Written in px it
  clips the moment someone raises their font size. → *judgement*
- **Flex and grid items that contain text need `min-width: 0`.** Their default
  floor is their own min-content, so they widen the page rather than let anything
  reflow. An `<input>` is worst: it carries a default `size` of 20 characters,
  which at a 200% root is over 400px. Three of these caused every pixel of
  horizontal scroll the app had. → *judgement*
- **Verify at 320, 560, 860 and 1280px, each at 100%, 150% and 200% root font
  size** — twelve combinations, zero horizontal overflow, zero clipping.
  → *manual*; set `document.documentElement.style.fontSize` to simulate
- **`em` in a media query is not the same thing.** It is relative to the
  *browser's default* font size, not to anything the page sets on `:root`. That
  makes it the right unit for "the text is large relative to the screen", and it
  also means an author-set root size cannot be used to test it.

### Adaptive rendering modes

- **Anything meaningful in a `background` or `box-shadow` must be restated under
  `@media (forced-colors: active)`**, in system colours (`Highlight`,
  `CanvasText`, `HighlightText`) — or opted out with `forced-color-adjust: none`
  where the *specific* colour is the information. Forced colours strips
  backgrounds, which for this app deletes the readings and leaves the layout
  looking perfectly fine.
  → `test_forced_colours_covers_everything_whose_background_is_data`
- **`prefers-contrast: more` re-points tokens on `:root` and nothing else.** If
  raising contrast needs a per-rule change, a colour is being set outside the
  token layer and the fix is to move it in.
  → `test_more_contrast_only_repoints_tokens`
- **Keep `color-scheme` accurate.** The palette is light-only; without saying so,
  UA widgets may render dark on a dark system.
  → `test_the_colour_scheme_is_declared`
- All three preference queries live in `css/adaptive.css`, imported last.
  → `test_the_preference_queries_are_present`

### The video overlay

`<canvas>` inherits nothing — not the cascade, not the type scale, and forced
colours does not touch it at all.

- **Only ask for a font the app bundles.** `ctx.font` uses its family string
  verbatim and falls back silently. This asked for IBM Plex Mono for a long
  time, a family that has never shipped here.
  → `test_canvas_text_uses_a_font_the_app_actually_ships`
- **Size from the root font size at draw time**, and derive every offset —
  padding, box height, baseline — as a ratio of it. Constants left behind make
  the box and the text separate as soon as the size changes.
  → `test_canvas_label_size_is_derived_from_the_root_font_size`
- **Route label colours through `readableTextColor()`** rather than hardcoding
  one, so there is a single place the decision is made.
  → `test_the_on_video_label_colour_comes_from_the_shared_decision`

---

## Standing decisions

Settled. Each is argued at the place it applies; this is an index, not a
restatement. Do not re-litigate without new information.

| Decision | Where the reasoning lives |
| --- | --- |
| Panel dots are decorative (each has an adjacent label), exempt from 1.4.11 | `css/tokens.css`, accent block |
| `--border` hairlines are decorative separation, exempt | `css/tokens.css`, on `--border-input` |
| The emotion groove keeps 1.24:1 — every row prints its value as text beside the bar | `css/emotions.css`, `.emo-track` |
| The input fill no longer carries the field boundary; its border does | `tests/support/contrast_check.py`, input pairs |
| The person swatch's boundary is a ring, not its hue | `css/sidebar.css`, `tests/support/contrast_check.py` |
| `.person-swatch` opts out of forced colours — the hue *is* the data | `css/adaptive.css` |
| `.subtitle-box` opts out of forced colours — it sits over video | `css/adaptive.css` |
| Okabe-Ito palette; the unknown grey separates by lightness, not hue | `js/state.js`, `tests/support/cvd_check.py` |
| A `19em` reflow block that was tried and removed | `css/responsive.css`, end of file |
| Touch targets of 36–41px at ≤560px rather than 44px | `css/responsive.css` — passes WCAG 2.2 AA (2.5.8 needs 24px); a deliberate AAA deviation |

---

## Known gaps

Nothing here is finished. Listed so it is visible rather than forgotten.

### Excluded by decision

**Subtitles are not a real caption track.** They are a `<div>` synced by
JavaScript, so they are invisible to assistive technology and to the browser's
own caption machinery, and `<video>` has no `<track>`. axe reports
`video-caption` as *incomplete* in every state and will keep doing so. The
transcript data to build WebVTT already exists.

**Person names are not in the on-video bounding-box labels.** This leaves a real
WCAG 1.4.1 gap: on the video, a box is identified *only* by hue, and the mapping
to a name exists solely in the sidebar swatch. For someone who cannot
distinguish two palette entries there is no second channel. The Okabe-Ito
palette and `cvd_check.py` mitigate this; they do not close it. That is why the
CVD check is a test and not a preference — it is the only defence there is.

### Never verified

**No screen reader has ever been run against this.** Everything automated
verifies the accessibility *tree*; what a screen reader announces from that tree
is a different question. Worth one pass with NVDA or Orca, in this order:

1. **Arrow-keying the video combobox** — the most likely thing to be subtly
   wrong despite correct markup, because `aria-activedescendant` support varies
   between screen reader and browser pairings.
2. Ask segment rows: reachable by Tab, activating on both Enter and Space.
3. Person rows: name and score not running together.
4. The two disclosure buttons: collapsed state, then the paragraph.
5. The scrubber: "Seek, slider, 0:00 of 3:27", not a number out of 1000.
6. The Ask button mid-request: still focused, reads as busy.

**Windows High Contrast has never been seen rendered.** The forced-colours rules
were verified as parsed with their declarations intact, through the CSSOM — a
mistyped system-colour keyword would have been dropped silently and shown up as
an empty declaration, and none were. That is not the same as looking at it.
Same for `prefers-contrast: more`.

### Not implemented

**There is no CI.** [a11y-ci.yml](a11y-ci.yml) is complete and YAML-validated
but inert where it sits; one `git mv` into `.github/workflows/` at the
repository root turns it on. It was left inert deliberately: the repository root
is a monorepo of a dozen unrelated subprojects, and switching on GitHub Actions
there affects all of them.

**The browser checks are not automated.** `a11y_browser_check.js` runs by hand
in a console. Driving it headlessly means adding a JavaScript toolchain and a
browser download to a repository that is Python end to end. The file ends with
the four lines of Playwright needed if that changes.

**No `lang` on foreign-language content.** The document is `lang="en"`, but the
transcripts, subtitles and emotion labels come from German-language video. WCAG
3.1.2 (Language of Parts) wants those marked `lang="de"` so a screen reader
switches pronunciation. This was not in the original audit and has not been
addressed. It affects `.subtitle-text` and anything rendering `clip_label`.

**No media keyboard shortcuts.** The player has a custom transport and no
`controls` attribute, so the browser's own keyboard handling (space to play,
arrows to seek) does not apply. Every control is reachable by Tab, so this is a
convenience gap rather than a barrier — but it is a gap.

**Filter changes are not announced.** Selecting a person rewrites all three
emotion panels with no live region, so a screen-reader user gets no confirmation
that anything happened. `aria-live="polite"` on the panels would be noisy at
every frame update; announcing the *filter change* specifically is the right
shape, and has not been done.

### Unclear, or wants a decision

**Is `aria-pressed` right for person rows?** They are currently toggle buttons.
A single-select `listbox` might describe "which person the panels are filtered
to" more accurately, but it is a bigger change and toggle buttons are not wrong.
Unresolved.

**The contrast registry is curated, not discovered.** Nothing detects a new
colour combination that nobody added. A stylesheet-walking version that finds
composited pairs automatically would be strictly better and is a real piece of
work.

**One literal is duplicated between the stylesheet and the checker** — the
`0.85` alpha in `.person-row.is-selected .person-meta` appears in both
`css/sidebar.css` and `tests/support/contrast_check.py`. Changing one
without the other silently re-opens the pair. It is commented in both
places; it is still a seam.

**The Ask agent is unavailable without `DUUI_QUERY_API_KEY`**, so two of the five
browser states are only reachable through the `fetch` stub built into
`a11y_browser_check.js`. That stub replaces the agent's *response* only — the
form submit and all rendered markup are the real code path — but it is a
simulation, and if the response shape ever changes the stub must change with it.
