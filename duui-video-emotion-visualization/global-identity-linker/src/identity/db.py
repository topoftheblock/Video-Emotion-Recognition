"""Database connections for the identity linker."""

import psycopg2
from psycopg2.extensions import connection

from .config import DB_CONFIG


def get_db_connection() -> connection:
    """Open a new database connection.

    The caller owns the connection and is responsible for closing it.
    """
    return psycopg2.connect(**DB_CONFIG)
