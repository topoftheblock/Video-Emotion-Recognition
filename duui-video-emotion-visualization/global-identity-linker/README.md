# global-identity-linker

Decides which people in different videos are the same person, and records the
answer as a global person.

Nothing else writes `persons.global_person_id`. The importer deliberately
leaves it NULL, so without this job every video's people stay isolated from
one another and the webapp has no cross-video panel to show.

It is a job, not a server: it runs, does the work, and exits. The database is
its entire input and output — it reads no CAS, opens no file, and writes
nothing to disk.

**The result is a similarity heuristic, not a verified identity.** People are
grouped by cosine distance between their embedding centroids: face first, and
voice only where the face comparison produced no match. Read a shared global
person as "probably the same person", and see the thresholds under
*Configuring it* before relying on the groupings for more than suggestions.

## Running it

From the stack root, with the database up:

```bash
docker compose run --rm global-identity-linker
```

It takes no arguments. Every global person is cleared and the whole corpus is
regrouped from scratch, so the result depends on what is in the database and
never on the order videos were imported in. That is also why it is not
automatic: the moment to run it is after a batch of imports, not during one.

Interrupting it is safe. The clear and the rebuild are one transaction, so an
interrupted run leaves the previous groupings exactly as they were.

Each person's nearest cross-video distance is written to
`persons.global_person_match_score` whether or not they were linked, so an
unlinked person can be inspected for how near the threshold it fell.

### Without the rest of the stack

The image builds from this directory alone:

```bash
docker build -t duui-video-emotion-visualization/global-identity-linker .
```

Running it needs a database carrying the schema and some embeddings in it.
Point `DUUI_DB_HOST` and the other credentials at yours.

Natively, on Python 3.14 with `requirements.txt` installed, `src` is the
source root rather than a package:

```bash
PYTHONPATH=src python -m identity
```

## Configuring it

Values and defaults are in [configuration.md](../docs/configuration.md). This
job reads five variables for the database — `DUUI_DB_NAME`, `DUUI_DB_USER`,
`DUUI_DB_PASSWORD`, `DUUI_DB_HOST`, `DUUI_DB_CONNECT_TIMEOUT` — and two of its
own:

| | |
| --- | --- |
| `DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD` | Maximum cosine distance for a face match |
| `DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD` | The same, for voices |

Lower is stricter: pgvector's cosine distance is 0 for identical vectors and 2
for opposite ones. **No derivation for either default is recorded in this
repository.** Retune them against duplicates you already know about in your own
material before trusting a grouping.

## Testing it

From the stack root:

```bash
docker compose run --rm tests global-identity-linker/tests
```

The suite builds small corpora directly in the database and asserts what gets
grouped: that similar faces link and dissimilar ones do not, that voice is the
fallback, that two people in one video are never linked to each other, and that
the outcome does not depend on the order rows were inserted in. Those tests run
against the empty database the runner
provisions; run `pytest` some other way and they skip, which the summary says
in as many words.

## Where the detail is

- **The layout.** `src/identity/` is the package. `linking.py` is the whole
  algorithm — centroids into a temp table, then a nearest-neighbor lookup per
  person. `job_runs.py` reports progress, `config.py` holds the thresholds,
  `db.py` opens the connection.
- **The columns it writes** — [database.md](../docs/database.md), under
  `global_persons` and `persons`.
- **The contracts it shares with the other parts** —
  [architecture.md](../docs/architecture.md).
