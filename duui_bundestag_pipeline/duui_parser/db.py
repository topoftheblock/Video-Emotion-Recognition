"""Database connection handling."""

import psycopg2

from .config import DB_CONFIG


def get_db_connection():
    """Open a new psycopg2 connection using DB_CONFIG."""
    return psycopg2.connect(**DB_CONFIG)
