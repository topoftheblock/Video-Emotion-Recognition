# To-do

Work that is wanted but not yet scheduled. Entries are added on request.

## Open

### Decide whether `schema.sql` should be idempotent throughout

It is idempotent for some of its statements and not for others. All fifteen
`CREATE INDEX` statements and the `job_runs` table are declared
`IF NOT EXISTS`; the other thirteen `CREATE TABLE` statements are not.

Re-running the file against a populated database therefore half-works: the
thirteen tables each fail with `relation "…" already exists`, `psql` continues
past the failures, and anything genuinely new is created. What
[operations.md](operations.md) tells you to do instead — apply the one
statement you actually mean — is unaffected either way.

Both halves have an argument:

- **Leave it.** The thirteen only ever run on an empty data directory, where
  nothing exists to collide with. `job_runs` is `IF NOT EXISTS` for a reason
  that does not apply to them: three services also create it. And without
  `IF NOT EXISTS`, a re-run says loudly that a table is already there, whereas
  with it a table whose *shape* has since changed is skipped in silence.
- **Change it.** A file whose halves behave differently is a trap for whoever
  reads one half and assumes the other, and thirteen errors are alarming for
  something that half-worked.

Deferred deliberately: it is a question about what the file should be, not a
defect with an obvious fix.

### Cover the Ask panel's tool-use loop

`webapp/src/backend/query_agent/agent.py` is the one coverage gap left open on
purpose. Testing it means stubbing the chat-completions client and asserting
against a conversation this project does not control, which is more work than
the rest of the test audit was.

### Cover the video payload route against a populated database

`webapp/src/backend/routes/videos.py` is half-covered. The untested half is the
payload route for a video that exists, which needs rows in the database. That
became reachable once `cas-to-postgres-importer` gained an end-to-end test that
imports the shipped sample, so the fixture to build on already exists.

## Referenced from elsewhere

Lists of outstanding work that live in other documents, kept linked here so
there is one place to look:

- [`webapp/docs/accessibility.md`](../webapp/docs/accessibility.md) — "what is
  still missing" from the accessibility work, including the browser checks that
  remain a manual procedure.
