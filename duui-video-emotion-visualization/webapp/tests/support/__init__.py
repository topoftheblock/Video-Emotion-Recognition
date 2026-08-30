"""Helper libraries the accessibility tests drive.

Nothing here is collected by pytest. Each module reads the committed
frontend — the stylesheets, the palette in `state.js`, the markup — and
reports what it found; the `test_*.py` modules beside this directory
hold the policy and do the asserting.

Two of them are also runnable on their own, which is a supported second
entry point and documented in webapp/docs/accessibility.md.
"""
