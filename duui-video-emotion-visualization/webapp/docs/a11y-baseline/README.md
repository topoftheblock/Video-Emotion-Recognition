# Accessibility baseline — Phase 0

Captured 2026-08-20, before any remediation work. Phase 6.1 re-runs all three
and diffs against these.

| File | Phase | What it is |
| --- | --- | --- |
| [contrast-baseline.txt](contrast-baseline.txt) | 0.1 | 82 colour pairs, 25 failing |
| [axe-baseline.md](axe-baseline.md) | 0.2 | axe-core 4.10.2 over five application states |
| [keyboard-sweep.md](keyboard-sweep.md) | 0.3 | the tab order, verified against real key presses |

## Reproducing

Every command below runs from the **stack root** (`../../../`),
which is two levels above this file — the paths in them are relative to it, not
to this directory.

**Contrast** — pure functions over committed values; no browser, no database.

```bash
docker run --rm -v "$PWD":/w -w /w python:3.14-slim python3 webapp/tests/support/contrast_check.py
```

The pytest gate that enforces it:

```bash
docker run --rm -v "$PWD":/w -w /w python:3.14-slim sh -c "pip install -q pytest psycopg2-binary && pytest webapp/tests/test_contrast.py -q"
```

`tests/test_contrast.py` carries a `KNOWN_FAILURES` baseline rather than
asserting zero failures, because every one of the 25 is still open. It fails on
a *new* failure, and it also fails when a known one starts passing — so each
phase strikes its own entries off, and the baseline is a progress ledger rather
than a suppression list.

**axe and the keyboard sweep** need the stack up:

```bash
docker compose up -d pgvector-db webapp
```

then drive `http://localhost:8010` in a browser. The exact states, the
`fetch` stub used to reach the two Ask states without an agent API key, and the
method for the sweep are documented in each file.

## Summary of the baseline

| Source | Findings |
| --- | --- |
| Contrast checker | 25 failing pairs, 6 recorded-but-exempt |
| axe-core | 4 violations (2 critical), identical in all five states; 2 incomplete |
| Keyboard sweep | 10 stops, 5 defects among them, 2 whole features absent from the order |

## Three findings Phase 0 added to the audit

The point of doing this before the fixes, rather than after, is that
instrumenting the app found things reading it did not.

1. **`region`** (axe) — `.ask-panel` is an unnamed `<section>`, so the Ask
   heading, input and results sit outside every landmark. → Phase 2.

2. **`person_1100%`** (sweep) — person rows concatenate the name and the match
   score with no separator, so the accessible name of stop 8 is `person_1100%`.
   → Phase 1.7.

3. **Two contrast pairs the audit missed** (checker) — placeholder text on the
   recessed input fill is 4.48:1, just under AA; and the emotion track groove is
   1.24:1 against the card, so the extent a fill is read as a proportion *of*
   has no perceivable boundary. → Phases 3.3 and 3.4.

Also worth carrying forward: **axe found none of the contrast failures and none
of the keyboard failures.** It checked nine text nodes page-wide and passed them
all, while the page was live-rendering a 2.18:1 chip. A clean axe report is not
evidence of an accessible page.
