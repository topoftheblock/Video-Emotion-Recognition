"""Deployment settings for the importer: paths, credentials, behavior.

Everything here is read from a `DUUI_*` environment variable, so every
value can differ between deployments. The UIMA vocabulary, which cannot,
lives in `cas/types.py`.

Each sub-project defines its own settings module from the same variable
names rather than sharing one; see docs/architecture.md for why, and
docker-compose.yml for where the values come from.
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

# --- File locations -----------------------------------------------------

# Where the pipeline drops its CAS files. A run given no path imports
# everything in here, so this is the "just run the importer" default for
# a whole batch. Read-only as far as the importer is concerned.
INPUT_XMI_DIR = os.environ.get("DUUI_INPUT_XMI_DIR", "cas")

# Where the video files those CAS files reference live. A separate
# setting from INPUT_XMI_DIR because the two need not sit together:
# point both at one directory for the side-by-side layout, or at
# different ones when the pipeline keeps them apart. Either way a CAS is
# matched to its video by the exact filename the CAS records — see
# cas/sofas.py — and never by position.
#
# Unset means "wherever the CAS files are" rather than a fixed default,
# so pointing the importer at a single directory of pipeline output
# takes one setting instead of two. docker-compose.yml chains the
# host-side mount the same way.
INPUT_VIDEO_DIR = os.environ.get("DUUI_INPUT_VIDEO_DIR") or INPUT_XMI_DIR

# Optional single-file default, kept for the older one-CAS-at-a-time
# workflow: when DUUI_XMI_FILE is set, a run given no path imports that
# one file instead of all of INPUT_XMI_DIR.
XMI_FILE = os.environ.get("DUUI_XMI_FILE")

# Which sofa holds the video, for when no video file exists in
# INPUT_VIDEO_DIR and it has to be recovered from the CAS itself (see
# cas/sofas.py). DUUI pipelines put the video on the `_InitialView` sofa
# and derive the other views from it, so that is the default. Set
# DUUI_VIDEO_VIEW when a pipeline routes it elsewhere — a dedicated
# `videoView`, say, the way audio lands on `audioView`. Any other
# `video/*` sofa is still tried as a fallback, so this only needs
# setting when the named view is genuinely different.
VIDEO_VIEW = os.environ.get("DUUI_VIDEO_VIEW", "_InitialView")

# What to do with a CAS whose video, by filename, is already in the
# database.
#
# `skip` leaves it alone and does not even load the CAS, which is what
# makes re-running the importer over a growing drop directory close to
# free. `replace` deletes the existing video and everything hanging off
# it — the schema cascades — then imports the file fresh, for when a CAS
# has been re-exported and its rows should match the new version.
#
# Overridable per run with `--on-existing`.
ON_EXISTING_CHOICES = ("skip", "replace")
ON_EXISTING = os.environ.get("DUUI_ON_EXISTING", "skip")

# Bundled non-code assets — the UIMA typesystem descriptors and the demo
# CAS — live under the source root's `resources/`, not in the `importer`
# package. Resolved from this file rather than the working directory so
# `python -m importer` works from anywhere. DUUI_TS_* still override.
RESOURCES_DIR = Path(__file__).resolve().parents[1] / "resources"
_TYPESYSTEM_DIR = RESOURCES_DIR / "typesystems"

TYPESYSTEM_FILES = {
    "identity_emotion": os.environ.get(
        "DUUI_TS_IDENTITY_EMOTION",
        str(_TYPESYSTEM_DIR / "IdentityEmotionTypeSystem.xml"),
    ),
    "multimodal_identity": os.environ.get(
        "DUUI_TS_MULTIMODAL_IDENTITY",
        str(_TYPESYSTEM_DIR / "MultimodalIdentityTypeSystem.xml"),
    ),
    "emotion": os.environ.get(
        "DUUI_TS_EMOTION", str(_TYPESYSTEM_DIR / "EmotionTypeSystem.xml")
    ),
}

# --- Video store --------------------------------------------------------

# The video store: the one place the importer (which copies into it, see
# cas/sofas.py) and the webapp (which reads from it, through its own
# copy of this setting) agree that the video for `videos.filename = X`
# lives at `<VIDEO_MEDIA_DIR>/X`.
#
# This is the output side, deliberately separate from the input
# directories above, so the webapp only ever sees videos belonging to a
# committed database row and never depends on how the raw drop
# directory is laid out.
#
# Defaults to the same value as the input directories, so a native
# (non-Docker) setup collapses the two into one directory and the copy
# step becomes a harmless no-op. Under Docker they are genuinely
# different: the importer reads /data/input/xmi and writes /data/videos,
# and the webapp mounts /data/videos read-only (see docker-compose.yml).
VIDEO_MEDIA_DIR = os.environ.get("DUUI_VIDEO_DIR", "cas")

# --- Database -----------------------------------------------------------

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
