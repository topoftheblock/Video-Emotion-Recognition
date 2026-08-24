# To-do

Work that is wanted but not yet scheduled. Entries are added on request.

## Open

<!-- Nothing recorded yet. -->

## Upgrade steps owed to users

Changes made here that an existing deployment has to apply by hand. These belong
in `docs/operations.md` when it is written.

- **The video store must be given to uid 1000.** The images stopped running as
  root, and a named volume keeps the ownership it was created with, so an
  existing store stays root-owned and the importer cannot write to it:
  `docker run --rm -v <project>_video_media:/v alpine chown -R 1000:1000 /v`.
  New deployments need nothing — an empty volume inherits ownership from the
  image.

## Referenced from elsewhere

Lists of outstanding work that live in other documents, kept linked here so
there is one place to look:

- [`webapp/docs/accessibility.md`](../webapp/docs/accessibility.md) — "what is
  still missing" from the accessibility work, including the browser checks that
  remain a manual procedure.
