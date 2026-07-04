"""Database connection handling and small generic SQL helpers."""

import psycopg2
from psycopg2 import sql

from .config import DB_CONFIG


def get_db_connection():
    """Open a new psycopg2 connection using DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)


def get_or_insert_id(cursor, conn, table, column, value):
    """
    Get an existing primary-key value or insert a new row and return it.

    Note: `conn` is currently unused (no commit happens here -- the
    caller controls the transaction) but is kept in the signature so
    call sites don't need to change if that ever becomes necessary.
    """
    if value is None:
        return None

    cursor.execute(
        sql.SQL("SELECT {} FROM {} WHERE {} = %s").format(
            sql.Identifier(column),
            sql.Identifier(table),
            sql.Identifier(column),
        ),
        (value,),
    )
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute(
        sql.SQL("INSERT INTO {} ({}) VALUES (%s) RETURNING {}").format(
            sql.Identifier(table),
            sql.Identifier(column),
            sql.Identifier(column),
        ),
        (value,),
    )
    return value
