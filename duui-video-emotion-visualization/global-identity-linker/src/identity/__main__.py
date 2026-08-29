# !/usr/bin/env python3
"""Entry point for the identity linker: `python -m identity`.

Takes no arguments. The corpus already in the database is the whole
input, every global person is cleared, and the groupings are rebuilt —
so this is what to run after importing new videos, since the importer
links nothing itself.

The clear and the rebuild are one transaction. An interrupted run rolls
back to the groupings that existed before it started, never to a corpus
that has been cleared and not rebuilt.

Settings come from `config.py` and are overridable through the `DUUI_*`
environment variables named there.
"""

import sys

from identity.db import get_db_connection
from identity.job_runs import JobRun
from identity.linking import recompute_global_identities


def _progress(index: int, total: int) -> None:
    """Print a progress line every hundred persons, and on the last one.

    Often enough that a long run does not look like a hang, rarely
    enough that the lines do not bury the summary printed at the end.
    """
    if index % 100 == 0 or index == total:
        print(f"  ...{index}/{total} persons processed")


def main() -> None:
    """Recompute every global person, reporting progress as it goes."""
    # JobRun writes its status row on its own autocommit connection, so
    # progress stays visible to the webapp while the recompute below
    # sits in a single uncommitted transaction.
    with JobRun("global-identity") as job:
        print("Connecting to database...")
        job.update(phase="connecting")
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            print("Clearing previous global persons and recomputing...")
            job.update(phase="comparing embeddings")

            def progress(index: int, total: int) -> None:
                _progress(index, total)
                # Called once per person. JobRun throttles its writes,
                # so this stays a counter rather than one database write
                # per person.
                job.update(current=index, total=total)

            stats = recompute_global_identities(cursor, progress=progress)
            job.update(phase="committing", force=True)
            conn.commit()
            cursor.close()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        job.update(
            message=(
                f"{stats['persons_linked']} of {stats['persons_total']} person(s) "
                f"linked into {stats['identities_created']} global person(s)"
            ),
            force=True,
        )

    print(
        f"\nCleared {stats['identities_deleted']} previous global person(s) "
        f"({stats['persons_unlinked']} person link(s) removed)."
    )
    print(
        f"Recomputed over {stats['persons_total']} person(s): "
        f"{stats['persons_linked']} linked into "
        f"{stats['identities_created']} global person(s)."
    )
    if stats["persons_total"] and not stats["persons_linked"]:
        print(
            "No cross-video links were found. That is expected with a single "
            "imported video, or when no face or voice embeddings were "
            "imported. Otherwise the distance thresholds "
            "(DUUI_GLOBAL_PERSON_*_DISTANCE_THRESHOLD) may be too strict."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # report it, don't dump a traceback
        print(f"[identity] ERROR: {exc}")
        sys.exit(1)
