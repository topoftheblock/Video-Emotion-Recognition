"""Deployment settings for the importer: paths, credentials, and behavior.

Everything here is read from a `DUUI_*` environment variable, so every value can
differ between deployments. The UIMA vocabulary, which cannot, lives in
`cas/types.py`.

Each sub-project defines its own settings module from the same variable names
rather than sharing one; see docs/architecture.md.
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

# --- File locations -------------------------------------------------

# Where the pipeline drops its CAS .xmi files. `python -m main`/
# `run_many()` with no explicit path argument import everything in
# here, so this is the "just run the importer" default for a whole
# batch. Read-only as far as this importer is concerned.
INPUT_XMI_DIR = os.environ.get("DUUI_INPUT_XMI_DIR", "cas")

# Where the video files those CAS files reference live. A separate
# setting from INPUT_XMI_DIR because the two do not have to sit
# together: point both at the same folder for the side-by-side layout,
# or at different folders when the pipeline keeps them apart. Either
# way a CAS is matched to its video by the exact filename the CAS
# records (see cas/sofas.py), never by position.
#
# Unset means "wherever the .xmi files are" rather than a fixed
# default, so pointing the importer at one folder of pipeline output
# needs one setting, not two. docker-compose.yml chains the host-side
# mount the same way.
INPUT_VIDEO_DIR = os.environ.get("DUUI_INPUT_VIDEO_DIR") or INPUT_XMI_DIR

# Optional single-file default, kept for compatibility with the older
# one-CAS-at-a-time workflow: if DUUI_XMI_FILE is set explicitly, a
# no-argument run imports just that file instead of all of
# INPUT_XMI_DIR.
XMI_FILE = os.environ.get("DUUI_XMI_FILE")

# Which CAS view/sofa holds the video, for the case where no video file
# exists in INPUT_VIDEO_DIR and it has to be recovered from the CAS
# itself (see cas/sofas.py). DUUI pipelines put the video on the
# `_InitialView` sofa and derive the other views from it, so that is
# the default; set DUUI_VIDEO_VIEW when a pipeline routes it elsewhere
# (e.g. a dedicated `videoView`, the way audio lands on `audioView`).
# Any other `video/*` sofa is still used as a fallback, so this only
# has to be set when the named view is genuinely different.
VIDEO_VIEW = os.environ.get("DUUI_VIDEO_VIEW", "_InitialView")

# What to do with a .xmi whose video (by filename) is already in the
# database. `skip` leaves it alone and does not even load the CAS --
# which is what makes re-running the importer over a growing drop
# folder close to free.
# `replace` deletes the existing video and everything hanging off it
# (the schema cascades) and imports the file fresh, for when a CAS has
# been re-exported and its rows should match the new version.
# Overridable per run with `--on-existing` on the command line.
ON_EXISTING_CHOICES = ("skip", "replace")
ON_EXISTING = os.environ.get("DUUI_ON_EXISTING", "skip")

# Bundled, non-code assets (the UIMA typesystem descriptors, the demo
# CAS) live under the source root's `resources/`, not in the `importer`
# package. Resolved from this file rather than the working directory so
# `python -m main` works from anywhere; DUUI_TS_* still override.
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

# --- Video media -------------------------------------------------------
# Where *served* video files live -- the one place both the importer
# (copies into it, see src/importer/cas/sofas.py) and the webapp (reads from it,
# see the viewer's src/backend/config.py copy of this setting) agree a
# video for `videos.filename = X` lives at `<VIDEO_MEDIA_DIR>/X`. This
# is the output side, deliberately separate from the input dirs above so the
# webapp only ever sees videos that belong to a committed DB row, and
# never depends on how the raw pipeline drop directory is laid out.
#
# Defaults to "cas" -- the same as the input dirs -- so a native (non-Docker)
# setup collapses the two into one directory and the copy step is a
# harmless no-op. In Docker they're genuinely different: the importer
# reads /data/input/xmi and writes /data/videos, and the webapp mounts
# /data/videos read-only (see docker-compose.yml).
VIDEO_MEDIA_DIR = os.environ.get("DUUI_VIDEO_DIR", "cas")

# --- Database ---------------------------------------------------------

DB_CONFIG = {
    "dbname": os.environ.get("DUUI_DB_NAME", "your_db"),
    "user": os.environ.get("DUUI_DB_USER", "your_user"),
    "password": os.environ.get("DUUI_DB_PASSWORD", "your_password"),
    "host": os.environ.get("DUUI_DB_HOST", "localhost"),
}
