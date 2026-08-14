"""
Central configuration for the global-identity job.

Deliberately separate from the importer's config (see
duui-video-emotion-cas-to-postgres/src/main/config.py) and the viewer's
(duui-video-emotion-visualization-webapp/src/backend/config.py): the
three containers are independent images with independent code, and
share nothing but the database. The settings they have in common --
DB_CONFIG here -- are defined in each of them from the same environment
variables, which is what keeps them pointing at the same Postgres (see
docker-compose.yml, where every service gets the same values).

This job reads no files and no CAS at all: the database is its entire
input and its entire output, so DB credentials plus the two distance
thresholds are the whole surface.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv is optional -- if it's not installed, real environment
    # variables (export FOO=bar, or set by your process manager) still
    # work fine; only the convenience of a local .env file is lost.
    pass

# --- Matching thresholds ----------------------------------------------
# Cosine distance (`<=>`, 0 = identical .. 2 = opposite) -- lower is
# stricter. 0.30 is a conservative starting point for ArcFace-style
# 512-dim face embeddings; retune against real cross-video duplicates
# before trusting this for anything beyond suggestions.
#
# There is no on/off switch here the way there used to be while this
# ran inside the importer: running this container *is* the opt-in.

GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD = float(
    os.environ.get("DUUI_GLOBAL_PERSON_FACE_DISTANCE_THRESHOLD", "0.30")
)
GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD = float(
    os.environ.get("DUUI_GLOBAL_PERSON_VOICE_DISTANCE_THRESHOLD", "0.35")
)

# --- Database ---------------------------------------------------------

DB_CONFIG = {
    "dbname": os.environ.get("DUUI_DB_NAME", "your_db"),
    "user": os.environ.get("DUUI_DB_USER", "your_user"),
    "password": os.environ.get("DUUI_DB_PASSWORD", "your_password"),
    "host": os.environ.get("DUUI_DB_HOST", "localhost"),
}
