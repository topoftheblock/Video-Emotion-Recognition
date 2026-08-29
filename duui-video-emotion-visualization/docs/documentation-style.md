# Documentation style

The single style every file in this project follows: Python, JavaScript, CSS,
SQL, Dockerfiles, Compose, Markdown, and user-facing output.

## The three rules

These override everything else here.

### 1. Write only what you can verify

Every statement must be checkable against the code, the database, the schema, a
test, or an authoritative external source. If it cannot be checked, it does not
go in.

### 2. The existing comments are not evidence

**The comments predating this documentation pass are unverified.** They are
legacy text: some accurate, some outdated, some simply wrong, with nothing to
tell them apart. A comment is therefore *never* a source for anything — not for
what the code does, and **not for why it does it**. Treat it as you would an
unsourced claim: verify it independently, or discard it.

This has a consequence that feels wasteful and is not: when an existing comment
states a reason, you may not carry that reason forward merely because it is
already written down. Either you can verify it, or it goes.

> The **frontend style and accessibility work** is the exception — and even
> there, keep it because it is *verifiable* (the palette claims are checked by
> `cvd_check.py` and `contrast_check.py`), not because a comment asserts it.

### 3. Never invent a rationale, and never assume one

If you cannot establish *why* something is the way it is: write what it does,
and say plainly that the reason is not recorded.

```python
# 0.30. No derivation for this value is recorded in this repository.
```

**If the reason matters and you cannot determine it, stop and ask.** Do not
guess, do not reason from plausibility, and do not let an existing comment
answer it for you. A confident-sounding reason nobody verified is worse than no
reason at all — the next reader cannot tell it apart from a real one, and that
is precisely how the current comments became untrustworthy.

### 4. Never describe the current corpus

**Documentation describes the software, not the data that happens to be loaded.**

Do not write row counts, id ranges, per-table totals, or "in the current corpus
there are N of these". Every one of those is a measurement of one database on one
day. It is stale the next time anything is imported, and a reader cannot tell a
stale number from a live one.

Write the **property** instead — the thing that stays true whatever is loaded:

```text
no    4,762 of the 40,323 distinct emotion ids occur in more than one video
yes   the same xmi:id can occur in more than one video
```

```text
no    all 7,068 tokens have a NULL segment_id
yes   a token may carry no segment link
```

This does not weaken rule 1. A measurement is **evidence** — it belongs in the
phase record that used it to decide something. A property is **documentation**,
and it is verified by a test or by the schema, both of which stay true as the
data changes.

### And write for a stranger

A reader who has not seen this file before, looking for one specific thing.

---

**Worked example.** A comment in `identity/config.py` described the face
threshold as tuned for "ArcFace-style 512-dimensional embeddings." Plausible,
and it survived several readings. The `models` table records what actually
produced the embeddings in the corpus: `w600k_r50` from InsightFace `buffalo_l`
— an ArcFace-family model, so the claim was *approximately* right, which is the
dangerous kind of wrong. The verifiable statement was available in the database
the whole time. Prefer it.

---

## 1. The comment budget

This is the rule that decides most edits, so it comes first.

**A comment must answer a question the code cannot.** In practice that is
*why*, never *what*.

Before writing or keeping a comment, apply this test:

> Could a competent reader work this out from the code in under ten seconds?

If yes, delete it. If no, keep it — and make it say the part they could not have
worked out.

### Delete on sight

```python
# Loop over the parsers
for step in PARSE_STEPS:          # the code says this
```

```python
# Increment the counter
count += 1  # the code says this
```

```python
def get_db_connection():
    """Open a new psycopg2 connection using DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)  # the signature says this
```

Also delete: commented-out code, `# TODO` with no owner or date, changelog
comments (`# added 2025-03, fixed in v2`) — that is what git is for — and any
comment describing behavior the code no longer has.

### Keep, because the code cannot say it

```python
# psycopg2 connections are thread-safe, cursors are not; the lock keeps
# the heartbeat thread and update() from opening cursors on the same
# connection at once.
self._lock = threading.Lock()
```

```python
# Mounted last: "/" is a catch-all, so anything registered after it
# would never be reached.
app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True))
```

Both survive the test: the reason is invisible in the code, and getting it wrong
causes a real bug.

### Length: the 8-line rule

**A comment longer than 8 lines belongs in `docs/`.** Leave a one-line summary
and a link:

```python
# Okabe-Ito: the only link between a box on the video and a name in the
# sidebar is color, so palette entries must stay distinguishable under
# color-vision deficiency. See webapp/docs/accessibility.md.
PERSON_COLORS = [...]
```

The rationale is not lost — it moves somewhere it can be read properly, with
room for the detail a code comment cannot carry. The threshold is deliberately
mechanical: an argument about whether *this* particular essay is worth keeping
is an argument you will have fifty times.

**Docstrings are exempt from the line count, not from the principle.** A module
docstring may run past 8 lines when it is genuinely describing what the module
owns. It may not run past 8 lines because it is arguing a design decision — that
still moves to `docs/`. The test is what the text is *doing*, not how long it is.

**Where moved rationale goes:** append it to the `docs/` page that owns the
subject (see the documentation map), and link to it from the code. If that page
does not exist yet, create it as a stub with the section you need — do not park
the text in a comment "for now", and do not link to a file that is not there.

### History goes, reasons stay

Delete anything explaining **how the code came to be**: what it used to do, what
was tried first, which bug prompted it, when it changed.

```python
# The previous palette had five such pairs -- teal/light-blue collapsed
# under tritanopia, teal/pink and orange/lime under deuteranopia...
```

Keep the *constraint* that still binds, drop the story of discovering it. If the
history is genuinely valuable, it goes in `docs/`, not above the code.

---

## 2. Python

### Docstrings — Google style

Summary on the **first** line, imperative mood, one sentence, ending in a period.

```python
def resolve_xmi_paths(paths: Iterable[str | Path]) -> list[Path]:
    """Expand files and directories into a sorted list of .xmi files.

    A directory contributes every `*.xmi` directly inside it. Recursion is
    deliberately not supported: a CAS and its companion video live side by
    side in one folder, so recursing would pick up unrelated corpora.

    Args:
        paths: Files, directories, or a mix of both.

    Returns:
        Absolute paths, sorted and de-duplicated.

    Raises:
        FileNotFoundError: If any path does not exist.
    """
```

Rules:

- **First line is a summary**, on the same line as the opening `"""`. Not a
  blank line — that is what most of this codebase currently does, and it is
  being changed.
- Blank line before any section.
- Sections in this order: `Args:`, `Returns:`, `Yields:`, `Raises:`.
- **No types in the docstring.** The annotations carry them (§2.2). Writing
  `paths (list): ...` duplicates the signature and drifts from it.
- **Omit a section that adds nothing.** A function whose summary already says
  what it returns does not need `Returns:`. Do not pad to fill the template.
- One-line docstrings stay one line: `"""Open a connection to the database."""`
- Every module gets a docstring: what it owns, and what it deliberately does
  not.

### Type annotations

Every function annotates its parameters and its return. Adopted in full — see
`docs/plan/README.md` §7.

```python
def parse_and_insert(
    cas: Cas,
    cursor: psycopg2.extensions.cursor,
    on_step: Callable[[str, int, int], None] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

- Modern syntax: `str | None`, `list[Path]`, `dict[str, Any]` — never
  `Optional[str]` or `typing.List`.
- `-> None` is written explicitly.
- If a type is genuinely unhelpful (`dict[str, Any]` for a free-form context),
  the *docstring* explains the shape. That is a real use of prose; describing
  `str` is not.
- **Module constants are annotated only when inference is wrong or unclear.**
  `MIN_WRITE_INTERVAL = 1.0` needs nothing; `DB_CONFIG: dict[str, str]` earns its
  annotation because the literal alone does not pin the value type.

### Constants

Plain `#` above the constant. **Not `#:`** — that is Sphinx attribute syntax,
and this project has no Sphinx build, so it is decoration.

```python
# Seconds between heartbeat writes. The webapp polls every two seconds,
# so anything finer is invisible.
MIN_WRITE_INTERVAL = 1.0
```

Related constants get **one comment each**, not one shared block above the
group — a shared block leaves each individual value undocumented, and the reader
arriving at the second constant has to scroll up and work out which sentence
applies to it.

### Section banners

For files with genuinely separate regions. One form only:

```python
# --- Database configuration ---------------------------------------------
```

Do not use them to divide a file into two sections; that is a sign the file
should be two files.

---

## 3. JavaScript

JSDoc, with types, checked by `tsc --checkJs --noEmit`. Every file starts with
`// @ts-check`.

```js
/**
 * Return the subtitle covering a playback position.
 *
 * @param {number} time - Playback position, in seconds.
 * @param {Segment[]} segments - Sorted by start time.
 * @returns {string|null} The subtitle text, or null between segments.
 */
```

- Same summary rule as Python: first line, imperative, one sentence.
- `@param {type} name - Description.` — hyphen separator, description
  capitalized, ending in a period.
- Shared shapes go in a `@typedef` rather than being spelled out repeatedly.
- The comment budget (§1) applies unchanged.

---

## 4. CSS

A header comment per file saying what it owns:

```css
/* Sidebar panels: people, cross-video matches, and the job banner. */
```

Section banners within a file use the same form as Python:

```css
/* --- Person rows ------------------------------------------------------ */
```

Comment a rule only when it is non-obvious *why* — a magic number, a browser
workaround, an accessibility constraint. Never restate the property.

---

## 5. SQL

`schema.sql` is the authoritative description of the database. Every table gets
a comment saying what one row represents; every non-obvious column gets one too.

```sql
-- One person as detected within a single video. The primary key is
-- (video_id, person_id): person_id comes from the CAS and is unique only
-- within its own video.
CREATE TABLE persons (
    ...
    -- Nearest cross-video centroid distance, written for every person
    -- whether or not they were linked. See docs/glossary.md#global-person.
    global_person_match_score DOUBLE PRECISION
);
```

---

## 6. Dockerfile, Compose, `.env.example`

- A header comment: what this image or service is, and how to build or run it.
- Comment any line whose *reason* is not obvious — an SELinux flag, a
  deliberately omitted dependency, a port choice.
- Do not comment `WORKDIR /app`.
- `.env.example` documents each variable in one or two lines. Anything longer
  belongs in the configuration reference, linked from the top of the file.

---

## 7. Markdown

- **US English.** `color`, `behavior`, `analyze`, `-ize` endings.
- Sentence case for headings: "Running the importer", not "Running The
  Importer".
- One sentence per line is *not* required; wrap prose at 80.
- Code blocks always carry a language tag.
- Links use descriptive text, never "click here" or a bare URL.
- Relative links between project documents, so they survive a move.

---

## 8. Mechanics

| | |
| --- | --- |
| **Language** | US English, everywhere, including code comments and log output |
| **Code line width** | 88 (the formatter enforces this) |
| **Prose line width** | 72 in comments and docstrings; 80 in Markdown |
| **Em dash** | `—`, not `--`. Files are UTF-8. Applies in code comments, docstrings, and user-facing strings alike — `--` was the legacy style. |
| **Quotes in prose** | Straight `"` and `'` |
| **Backticks** | Around identifiers, filenames, and literal values |
| **File references** | Repo-relative: `webapp/src/backend/app.py`, not `app.py` |

Prose wraps narrower than code on purpose: long lines of explanation are harder
to read than long lines of code, and the codebase already wraps prose near 72
(measured p90 = 71).

**72 is the hard rule for comments and docstrings, not a target.** Applying the
guide to the first sub-project produced 212 prose lines wrapped at 88 — every
one of them written while the rule said 72. Nothing in the linter enforces it
(`E501` fires at 88, and only for Python), so it holds only if it is checked
deliberately. The one exception is a **section banner, which runs to column
74**, matching the form in §7; it is a rule, not prose.

---

## 9. User-facing output

Log lines, error messages, and CLI output are documentation and follow the same
rules: US English, the glossary's vocabulary, no invented synonyms.

- Say what happened and what it means, not just that something failed.
- Prefix with the component: `[importer]`, `[webapp]`, `[identity]`.
- **A message must not claim work that has not happened yet.** Print
  "Loading CAS data from X" when the load begins, not before deciding whether to
  skip the file.

---

## 10. Terminology

One name per concept, defined in **[glossary.md](glossary.md)**. It is binding
on code, comments, documentation, and user-facing output alike. When the code
and the glossary disagree, the glossary wins and the code is renamed — but the
database schema is the reason the glossary says what it says.
