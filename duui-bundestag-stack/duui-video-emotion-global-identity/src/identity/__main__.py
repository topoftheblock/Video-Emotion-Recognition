#!/usr/bin/env python3
"""
Entry point for the cross-video global-identity job.

`src/` is the source root (it goes on the path, it is not a package),
so this runs as the `identity` package's entry module -- with `src/` on
PYTHONPATH, or from inside it:

    python -m identity

It takes no arguments: the whole corpus already in the database is the
input. Every existing global identity is cleared and the groupings are
recomputed from scratch, so this is the thing to re-run after importing
new videos -- the importer itself no longer links anything.

The wipe and the rebuild are one transaction: an interrupted run rolls
back to the identities you had before it started, never to a corpus
that has been cleared but not rebuilt.

Configuration (DB credentials, distance thresholds) is read from
src/identity/config.py, and can be overridden via the environment
variables listed there (DUUI_DB_NAME, DUUI_GLOBAL_PERSON_*, etc.)
"""

import sys

from identity.db import get_db_connection
from identity.linking import recompute_global_identities


def _progress(index, total):
    # One line per 100 people (and on the last one) -- a real corpus is
    # thousands of persons, and a line each would bury the summary,
    # while total silence for minutes looks like a hang.
    if index % 100 == 0 or index == total:
        print(f"  ...{index}/{total} persons processed")


def main():
    print("Connecting to database...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        print("Clearing previous global identities and recomputing...")
        stats = recompute_global_identities(cursor, progress=_progress)
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(
        f"\nCleared {stats['identities_deleted']} previous global "
        f"identit{'y' if stats['identities_deleted'] == 1 else 'ies'} "
        f"({stats['persons_unlinked']} person link(s) removed)."
    )
    print(
        f"Recomputed over {stats['persons_total']} person(s): "
        f"{stats['persons_linked']} linked into "
        f"{stats['identities_created']} global identit"
        f"{'y' if stats['identities_created'] == 1 else 'ies'}."
    )
    if stats["persons_total"] and not stats["persons_linked"]:
        print(
            "No cross-video links were found. That is the expected result "
            "for a single imported video, or if no face/voice embeddings "
            "were imported; otherwise the distance thresholds "
            "(DUUI_GLOBAL_PERSON_*_DISTANCE_THRESHOLD) may be too strict."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- report, don't traceback-dump
        print(f"[duui_global_identity] ERROR: {exc}")
        sys.exit(1)
