"""Deployment settings for the webapp: paths, credentials, the agent.

Every setting the webapp reads lives here, so nothing else in the image
hard-codes a path or a credential.

Deliberately separate from the importer's own settings module: the two
are independent images with independent code, sharing nothing but the
database and the video store. The values they *both* read are defined
in each of them from the same environment variables, which is what
keeps the two ends of those contracts pointing at the same place; see
docker-compose.yml, where both services are given the same values.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Optional. Without it, environment variables set by the shell or
    # the process manager still work; only .env file support is lost.
    pass

# --- Video store --------------------------------------------------------

# The video store: the one place the importer, which copies into it,
# and the webapp, which reads from it, agree that the video for
# `videos.filename = X` lives at `<VIDEO_MEDIA_DIR>/X`. The webapp
# never sees the importer's input directory at all.
#
# Defaults to the same value the importer defaults its input directory
# to, so a native (non-Docker) setup collapses the two into one
# directory and the importer's copy step becomes a harmless no-op.
# Under Docker they are genuinely different: the importer writes
# /data/videos, and the webapp mounts it read-only.
VIDEO_MEDIA_DIR = os.environ.get("DUUI_VIDEO_DIR", "cas")

# Resolved once, here, so that the routes checking whether a video's
# file is present and the `/media` mount serving it cannot drift apart.
# Creating the directory is deliberately not done at import time:
# `create_app` does that, so importing this package touches no
# filesystem.
VIDEO_DIR = Path(VIDEO_MEDIA_DIR).resolve()

# --- Frontend -----------------------------------------------------------

# The HTML, CSS and JavaScript served as static files: a sibling of
# this package under the source root. The whole source tree is copied
# verbatim into the image, so this resolves identically in the
# repository and in the container.
STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend"

# --- Database -----------------------------------------------------------

# The same Postgres the importer and the linker write into. The webapp
# reads it, with one exception: it creates `job_runs` at startup if the
# database predates that table — see `queries/jobs.py`.
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

# --- Query agent --------------------------------------------------------

# The "Ask" panel talks to an OpenAI-compatible chat-completions
# endpoint. The default points at a university-hosted gateway; set
# DUUI_QUERY_BASE_URL and DUUI_QUERY_MODEL to use a different
# OpenAI-compatible provider.
#
# Leave DUUI_QUERY_API_KEY empty and the panel reports itself as
# unconfigured, while the rest of the webapp works unchanged.
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
