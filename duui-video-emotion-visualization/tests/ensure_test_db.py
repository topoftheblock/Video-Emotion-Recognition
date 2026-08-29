"""Create the test database if it is missing, and apply the schema.

The suite needs a database with the schema and no rows: the DB-backed
tests assume they are the only writer, and several of them fail against
a populated corpus rather than skipping. Nothing else creates that
database — losing it to a rebuild is what silently turned a 150-pass run
into 121 passed and 29 skipped once already.

Run by the `tests` service before pytest. Safe to run repeatedly.
"""

import os
import sys

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

SCHEMA = "/app/pgvector-db/schema.sql"


def main() -> int:
    """Create the test database and apply the schema, if needed.

    Returns:
        A process exit status.
    """
    name = os.environ["DUUI_DB_NAME"]
    conn_args = {
        "user": os.environ.get("DUUI_DB_USER", "duui"),
        "password": os.environ.get("DUUI_DB_PASSWORD", "duui"),
        "host": os.environ.get("DUUI_DB_HOST", "pgvector-db"),
        # The same knob the three services read, so the project has
        # one value rather than two that can drift apart.
        "connect_timeout": int(os.environ.get("DUUI_DB_CONNECT_TIMEOUT", "10")),
    }

    # Connect to `postgres` rather than the target: CREATE DATABASE
    # cannot run from inside the database it is creating.
    admin = psycopg2.connect(dbname="postgres", **conn_args)
    admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            if cur.fetchone():
                print(f"[tests] {name} already exists")
                return 0
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            print(f"[tests] created {name}")
    finally:
        admin.close()

    with open(SCHEMA, encoding="utf-8") as handle:
        schema_sql = handle.read()

    fresh = psycopg2.connect(dbname=name, **conn_args)
    fresh.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with fresh.cursor() as cur:
            cur.execute(schema_sql)
        print(f"[tests] applied schema.sql to {name}")
    finally:
        fresh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
