"""Configuration: database credentials and matching thresholds.

The database is this job's entire input and output — it reads no files
and no CAS — so these settings are its whole external surface.

Each sub-project defines its own configuration from the same `DUUI_*`
environment variables rather than sharing a module; see
docs/architecture.md for why, and docker-compose.yml for where the
values come from.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Optional. Without it, environment variables set by the shell or
    # the process manager still work; only .env file support is lost.
    pass

# --- Matching thresholds ------------------------------------------------

# Maximum cosine distance at which two face embeddings are taken to be
# the same person. pgvector's `<=>` returns 0 for identical vectors and
# 2 for opposite ones, so a lower value is stricter.
#
# No derivation for 0.30 is recorded in this repository. Which model
# produced a given embedding is recorded per row, in `models`.
GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD = float(
    os.environ.get("DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD", "0.30")
)

# The same, for voice embeddings. Looser than the face threshold; no
# derivation for either value is recorded in this repository.
GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD = float(
    os.environ.get("DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD", "0.35")
)

# --- Database -----------------------------------------------------------

# Keyword arguments for psycopg2.connect().
#
# The defaults are placeholders that cannot connect to anything. Whether
# that is deliberate (fail rather than reach an unintended database) or
# simply an unfinished template is not recorded anywhere in this
# repository. It does have one known consequence: on a host with no
# DUUI_DB_* set, every database-backed test skips instead of running.
# Seconds to wait for the connection itself. Without it, psycopg2 waits
# on the operating system's TCP timeout: against a host that accepts the
# route but never answers, that is minutes with nothing printed. Ten
# turns that hang into a clean OperationalError. It bounds the connect
# only, never a query that is already running.
DB_CONNECT_TIMEOUT = int(os.environ.get("DUUI_DB_CONNECT_TIMEOUT", "10"))

DB_CONFIG: dict[str, str | int] = {
    "dbname": os.environ.get("DUUI_DB_NAME", "your_db"),
    "user": os.environ.get("DUUI_DB_USER", "your_user"),
    "password": os.environ.get("DUUI_DB_PASSWORD", "your_password"),
    "host": os.environ.get("DUUI_DB_HOST", "localhost"),
    "connect_timeout": DB_CONNECT_TIMEOUT,
}
