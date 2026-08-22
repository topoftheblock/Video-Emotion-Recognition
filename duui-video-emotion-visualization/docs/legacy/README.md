# Legacy documents

**Nothing in this directory is a source for anything.** These files predate the
documentation rebuild. Their claims are unverified and some are known to be
wrong. They are kept for one reason only: as a checklist of the *topics* the new
documentation needs to cover.

Do not cite them, do not copy from them, and do not resolve a question by
reading them. Where they conflict with the code, the code is right.

| File | Was | Status |
| --- | --- | --- |
| [`README-original.md`](README-original.md) | The root `README.md`, 968 lines | Superseded. Retained as a topic checklist for the rewrite. |
| [`data-schema-design.md`](data-schema-design.md) | `pgvector-db/data_schema_with_types.md` | Its database content is being moved into [`../database.md`](../database.md). |

## What happens to them

Both are deleted once the documentation rebuild is finished. Their useful
content will have moved:

- The root README's material is redistributed across the new `README.md`,
  [`../architecture.md`](../architecture.md),
  [`../configuration.md`](../configuration.md) and
  [`../operations.md`](../operations.md), per the map in
  [`../README.md`](../README.md).
- The design document's table and column descriptions move into
  [`../database.md`](../database.md), written from `pgvector-db/schema.sql`
  rather than from the design.

One thing worth knowing before relying on the design document for anything: it
describes a `FusedEmotion` layer that has no tables, no importer support, and no
trace anywhere else in the project.
