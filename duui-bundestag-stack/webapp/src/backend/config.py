"""
Central configuration for the viewer.

Every setting the webapp reads lives here, so nothing else in this
container hardcodes a path or a credential inline.

Deliberately separate from the importer's own config (see
cas-to-postgres-importer/src/main/config.py): the two
containers are independent images with independent code, and share
nothing but the database and the video store. The settings they *both*
read -- DB_CONFIG and VIDEO_MEDIA_DIR -- are defined in each of them
from the same environment variables, which is what keeps the two ends
of those two contracts pointing at the same place (see
docker-compose.yml, where both services get the same values).
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv is optional -- if it's not installed, real environment
    # variables (export FOO=bar, or set by your process manager) still
    # work fine; only the convenience of a local .env file is lost.
    pass

# --- Video media -------------------------------------------------------
# Where *served* video files live -- the one place both the importer
# (copies into it, see
# cas-to-postgres-importer/src/main/media.py) and the webapp
# (reads from it, see backend/routes/videos.py) agree a video for
# `videos.filename = X` lives at `<VIDEO_MEDIA_DIR>/X`. The viewer only
# ever reads from it; it never sees the importer's input directory at
# all.
#
# Defaults to "cas" -- the same default the importer uses for its input
# directory -- so a native (non-Docker) setup collapses the two into one
# directory and the importer's copy step is a harmless no-op. In Docker
# they're genuinely different: the importer reads /data/input/xmi and writes
# /data/videos, and the webapp mounts /data/videos read-only (see
# docker-compose.yml).
VIDEO_MEDIA_DIR = os.environ.get("DUUI_VIDEO_DIR", "cas")

# Resolved once, here, so the routes that check "is this video's file
# actually present" and the /media static mount cannot drift apart.
# Creating it is deliberately NOT done at import time -- create_app()
# does that, so importing this package never touches the filesystem.
VIDEO_DIR = Path(VIDEO_MEDIA_DIR).resolve()

# --- Frontend ---------------------------------------------------------
# The HTML/CSS/JS served as static files: a sibling of this package
# under the source root (src/backend/ -> src/frontend/). The whole src/
# tree is copied verbatim into the image, so this resolves identically
# in the repo and in the container.
STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend"

# --- Database ---------------------------------------------------------
# The same Postgres the importer writes into; the viewer only reads.

DB_CONFIG = {
    "dbname": os.environ.get("DUUI_DB_NAME", "your_db"),
    "user": os.environ.get("DUUI_DB_USER", "your_user"),
    "password": os.environ.get("DUUI_DB_PASSWORD", "your_password"),
    "host": os.environ.get("DUUI_DB_HOST", "localhost"),
}

# --- Natural-language query agent -------------------------------------
# Talks to an OpenAI-compatible chat-completions endpoint (this project
# uses a university-hosted Open WebUI/Ollama gateway serving Qwen3-VL,
# not Anthropic directly -- swap DUUI_QUERY_BASE_URL/DUUI_QUERY_MODEL to
# point at a different OpenAI-compatible provider if needed).
#
# Leave DUUI_QUERY_API_KEY empty and the "Ask" panel reports itself as
# unconfigured while the rest of the viewer works unchanged.

QUERY_AGENT_API_KEY = os.environ.get("DUUI_QUERY_API_KEY", "")
QUERY_AGENT_BASE_URL = os.environ.get(
    "DUUI_QUERY_BASE_URL", "https://lehre.llm.texttechnologylab.org/api"
)
QUERY_AGENT_MODEL = os.environ.get("DUUI_QUERY_MODEL", "gondor.qwen3-vl:32b")
QUERY_AGENT_MAX_ROWS = int(os.environ.get("DUUI_QUERY_MAX_ROWS", "500"))
QUERY_AGENT_STATEMENT_TIMEOUT_MS = int(
    os.environ.get("DUUI_QUERY_STATEMENT_TIMEOUT_MS", "8000")
)
QUERY_AGENT_MAX_TOOL_ITERATIONS = int(
    os.environ.get("DUUI_QUERY_MAX_TOOL_ITERATIONS", "6")
)
