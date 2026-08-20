# Keyboard sweep baseline

Phase 0.3 of [../accessibility-plan.md](../accessibility-plan.md).
Captured 2026-08-20 against `http://localhost:8010` in the default state
(video `teil_007.mp4`, three identified people, no person selected).

This is the artefact Phase 1 is measured against.

## Method

The order below was computed from the DOM (focusable elements in document
order; the page has **zero** positive `tabindex` values) and then **verified
against twelve real `Tab` presses**. The observed sequence matched the computed
one exactly and wrapped back to stop 1 after stop 10, so there is no focus trap
and no order surprise.

Accessible names were resolved by the standard precedence — `aria-label`,
`aria-labelledby`, `label[for]`, wrapping `<label>`, contents, `title`,
`placeholder` — and the source of each name is recorded, because *where* a name
comes from is what several Phase 1 items are about.

## The order — 10 stops

| # | Region | Element | Role | Announced name | Name comes from | State |
|---|---|---|---|---|---|---|
| 1 | header | `#videoComboInput` | `combobox` | "Video" | `aria-label` | `expanded=false` |
| 2 | ask | `#askInput` | textbox | "e.g. \"where do video emotion…\"" | **placeholder** ⚠ | – |
| 3 | ask | `#askSubmit` | button | "Ask" | contents | – |
| 4 | ask | `#askReset` | button | "Reset view" | contents | – |
| 5 | stage | `#playBtn` | button | "Play/Pause" ⚠ | `aria-label` | – |
| 6 | stage | `#subtitleToggle` | button | "CC" | contents | `pressed=true` |
| 7 | stage | `#scrub` | slider | **(none)** ⚠ | – | – |
| 8 | sidebar | `.person-row` | button | "person_1100%" ⚠ | contents | `pressed=false` |
| 9 | sidebar | `.person-row` | button | "person_233%" ⚠ | contents | `pressed=false` |
| 10 | sidebar | `.person-row` | button | "person_366%" ⚠ | contents | `pressed=false` |

## What the sweep shows

**Reaching the player takes five stops.** Every route to the transport runs
through the whole Ask panel first. Phase 2.2's skip link is what fixes this.

**Stop 7 has no name at all.** `#scrub` announces as "slider, 0" — nothing says
it seeks, and its value is a position out of 1000 with no relation to the video
clock. Phase 1.3.

**Stop 2's name is a placeholder**, which disappears on the first keystroke.
Phase 1.2. Note axe passes this (see the axe baseline) — it is only visible
here.

**Stop 5 announces both states permanently.** "Play/Pause" never changes,
though the icon does. Phase 1.4. Contrast with stop 6, which correctly reports
`pressed=true` and retitles itself — that is the pattern to copy.

**Stops 8–10 run the name into the score.** `person_1` + `100%` with no
separator in the markup produces the accessible name `person_1100%` — a screen
reader says "person eleven hundred percent". `js/panels/people.js` interpolates
the score span immediately after the name text with no whitespace between them.

> This is **not** in the audit and is new here. It is a one-character fix in the
> same template Phase 1.7 already opens, and the same pattern should be checked
> in the cross-video list.

## What is missing from the order entirely

**The Ask segment results.** With three segments rendered, the sweep still
reports **10 stops** and **zero** focusable elements inside `#askResults`. The
`<li>` elements carry a click handler and nothing else — no `role`, no
`tabindex`, no key handler. The app's headline feature cannot be operated
without a pointer. Phase 1.1.

**The match-confidence explanations.** Both `.person-legend` blocks hold their
text in `title` on a non-focusable `<div>`, so they appear at no stop in this
table. The information is unreachable by keyboard. Phase 1.7.

**The emotion panel content**, correctly — it is a read-out, not a control, and
nothing there should take focus.

## Focus indicators

Every stop that has a `:focus-visible` rule shows a 2px `--signal` outline at
5.84:1 against the card, which passes 1.4.11. Stops 1 and 2 instead suppress
the outline and draw a `box-shadow` ring; that reads fine now but is the reason
Phase 4.2 has to add an `outline` fallback, since `box-shadow` is dropped under
forced colours.

Nothing in the sweep was focusable-but-invisible, and no stop was reachable
without a visible indicator.

## Re-running this

Phase 6.1 should reproduce the table above and expect: a skip link at stop 1,
three new stops for the segment list in the Ask-results state, a named slider,
a state-tracking play button, and clean separation between person names and
their scores.
