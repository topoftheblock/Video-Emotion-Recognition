# axe-core baseline

Phase 0.2 of [../accessibility.md](../accessibility.md).
Captured 2026-08-20 against the running stack. Re-run this before Phase 6.1
and diff.

## How this was captured

| | |
|---|---|
| Tool | axe-core 4.10.2, loaded from CDN into the live page |
| Target | `http://localhost:8010` (compose `webapp` service, real Postgres, 10 imported videos) |
| Rule tags | `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`, `best-practice` |
| Viewport | desktop default |

Five states, not the three the plan named — the default entry state and the
open combobox were free to capture and the combobox is where Phase 1.5 lives.

| State | How it was reached |
|---|---|
| A — default | page load |
| B — person filter active | click the first `.person-row` |
| C — Ask result with segments | submit the Ask form with a stubbed agent response |
| D — Ask result with table | as C, with a response carrying no `video_id`/`start_time`/`end_time` |
| E — combobox open | focus `#videoComboInput`, press ArrowDown twice |

**On the stub.** This stack has no `DUUI_QUERY_API_KEY`, so `POST /api/ask`
answers `422` and states C and D are unreachable by asking a real question.
Only the *agent's response* is stubbed, at the `fetch` boundary: the form
submit, `renderAskResults()`, and every element axe then scans are the real
code path. Nothing in the frontend knows the difference.

## Violations

The same four violations appear in **every** state — none of them is
state-dependent, and no state introduced one of its own.

| Rule | Impact | Nodes | Target | Plan |
|---|---|---|---|---|
| `aria-allowed-attr` | critical | 1 | `#videoSelect` | 1.5 |
| `label` | critical | 1 | `#scrub` | 1.3 |
| `page-has-heading-one` | moderate | 1 | `html` | 2.1 |
| `region` | moderate | 2–3 | `.ask-heading > div`, `#askInput`, `#askResults` | **new** |

`aria-allowed-attr` is the Phase 1.5 finding seen from the other side:
`js/videoLoader.js` writes `aria-expanded` onto the `#videoSelect` **div**,
which has no role and therefore may not carry it. Confirmed live in state E —
the div reads `aria-expanded="true"` while the input that actually has
`role="combobox"` still reads `"false"`.

`region` is **not** in the audit and is new here. `.ask-panel` is a bare
`<section>`; an unnamed `section` is not a landmark, so the Ask heading, the
input and the results all sit outside every landmark. Fixing it is one
`aria-labelledby` pointing at `.ask-title` — worth folding into Phase 2, which
already opens the document-structure question.

## Incomplete (needs a human decision, not a fix)

| Rule | Target | Disposition |
|---|---|---|
| `video-caption` | `#player` | **Out of scope.** This is the excluded subtitles-as-`<track>` finding. Expect it to persist; do not treat it as a regression. |
| `aria-toggle-field-name` | `.video-combo-item` | Real, and adjacent to Phase 1.5. `<label class="video-picker">` wraps the *entire* combobox including the `role="listbox"`, so the label text can be pulled into each option's name. Consider unwrapping the label while rewiring the ARIA. |

## What axe did not catch

This matters more than the list above, because it is the argument for the other
two Phase 0 deliverables existing at all.

**Every contrast failure.** `color-contrast` ran in all five states and reported
**pass**. It examined nine text nodes page-wide:

```
.topbar-mark  .topbar-title  label > span  #videoComboInput
.ask-title    .ask-subtitle  #askInput     .btn-label      #askReset
```

The topbar and the Ask panel, and nothing else — no sidebar, no emotion panel,
no stage. In state B the page was live-rendering `person_1`'s filter chip as
white on `#e0a458` (**2.18:1**, confirmed by reading the computed styles) and
the selected row's score at `rgba(255,255,255,0.75)` over `--signal`
(**3.99:1**). axe flagged neither. It also does not check non-text contrast at
all, so all 13 swatch failures are invisible to it.
`tests/support/contrast_check.py` covers 82 pairs and catches all of them.

**The mouse-only Ask segment list.** In state C, three `<li>` elements each
carry a click handler and no role, no `tabindex`, no key handling. axe reported
nothing, and cannot: a click listener on a non-interactive element leaves no
signal in the accessibility tree. This is the single most severe finding in the
audit, and it is only visible from the keyboard sweep.

**The unlabelled Ask input.** axe passes `#askInput` because the accname spec
accepts `placeholder` as a last-resort name. It is still the Phase 1.2 finding:
the name vanishes the moment the user types.

**The static play button label.** `aria-label="Play/Pause"` is a name, so axe is
satisfied; that it never changes is not machine-checkable.

Treat a clean axe report as necessary and nowhere near sufficient.
