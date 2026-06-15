"""
DUUI REST wrapper for the Phase-1 Emotion component.

Exposes the four DUUI-required endpoints:
    GET  /v1/typesystem         -> TypeSystem XML
    GET  /v1/communication_layer -> Lua script
    GET  /v1/documentation      -> annotator metadata
    POST /v1/process            -> run emotion analysis on one phase1-JSON payload
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, Optional

from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

# ---- re-use all logic from the standalone script ----------------------------
from duui_emotion import EmotionConfig, run as emotion_run, load_recognizer

# ============================================================
#  Settings (injected via ENV / Docker --build-arg / -e)
# ============================================================
ANNOTATOR_NAME    = os.environ.get("DUUI_EMOTION_ANNOTATOR_NAME",    "duui-emotion-hsemotion")
ANNOTATOR_VERSION = os.environ.get("DUUI_EMOTION_ANNOTATOR_VERSION", "0.1.0")
LOG_LEVEL         = os.environ.get("DUUI_EMOTION_LOG_LEVEL",         "INFO")

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)
logger.info("Starting %s  v%s", ANNOTATOR_NAME, ANNOTATOR_VERSION)

# ============================================================
#  Pre-load model once at startup (not per request)
# ============================================================
_cfg = EmotionConfig()
logger.info("Pre-loading HSEmotion model …")
_fer = load_recognizer(_cfg)
logger.info("Model ready.")

# ============================================================
#  Load static files
# ============================================================
_RESOURCES = os.path.join(os.path.dirname(__file__),
                           "..", "..", "resources")
_LUA_DIR   = os.path.join(os.path.dirname(__file__),
                           "..", "..", "lua")

with open(os.path.join(_RESOURCES, "TypeSystem.xml"), "rb") as f:
    _typesystem_xml: bytes = f.read()

with open(os.path.join(_LUA_DIR, "duui_emotion.lua"), "r", encoding="utf-8") as f:
    _lua_script: str = f.read()

# ============================================================
#  Request / Response models
# ============================================================
class DUUIRequest(BaseModel):
    """
    Mirrors the phase1.json structure.
    DUUI sends the CAS payload as JSON (serialised by the Lua script).
    """
    video: dict
    face_identities: list[dict]
    tracks: list[dict]
    face_detections: list[dict]


class DUUIResponse(BaseModel):
    """
    List of serialised Emotion objects written back to the CAS via Lua.
    """
    emotions: list[dict]
    model: str


# ============================================================
#  FastAPI app
# ============================================================
app = FastAPI(
    title=ANNOTATOR_NAME,
    description="HSEmotion-based facial emotion analysis for DUUI (Phase-1 video graph)",
    version=ANNOTATOR_VERSION,
    terms_of_service="https://www.texttechnologylab.org/legal_notice/",
    contact={"name": "TTLab Team", "url": "https://texttechnologylab.org"},
    license_info={"name": "AGPL", "url": "http://www.gnu.org/licenses/agpl-3.0.en.html"},
)


@app.get("/v1/communication_layer", response_class=PlainTextResponse)
def get_communication_layer() -> str:
    """Return the Lua serialise/deserialise script."""
    return _lua_script


@app.get("/v1/typesystem")
def get_typesystem() -> Response:
    """Return the UIMA TypeSystem XML."""
    return Response(content=_typesystem_xml, media_type="application/xml")


@app.get("/v1/documentation")
def get_documentation() -> dict:
    """Return annotator metadata."""
    return {
        "annotatorName":    ANNOTATOR_NAME,
        "annotatorVersion": ANNOTATOR_VERSION,
        "model":            _cfg.model_name,
    }


@app.post("/v1/process")
def post_process(request: DUUIRequest) -> DUUIResponse:
    """
    Run the emotion pipeline on the supplied phase1 payload.

    The video file must be reachable inside the container at the path given in
    request.video["path"].  Mount it via  -v /host/path:/data  and set
    "path": "/data/clip.mp4"  in the JSON.
    """
    # Write the request payload to a temporary JSON file so we can reuse
    # the existing run() function which reads from disk.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False, encoding="utf-8") as tmp:
        json.dump({
            "video":           request.video,
            "face_identities": request.face_identities,
            "tracks":          request.tracks,
            "face_detections": request.face_detections,
        }, tmp)
        tmp_path = tmp.name

    try:
        # Write output to a temp file as well, then read it back
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out_tmp:
            out_path = out_tmp.name

        cfg = EmotionConfig(out_path=out_path)
        emotion_run(tmp_path, cfg)

        with open(out_path, "r", encoding="utf-8") as f:
            result = json.load(f)

    finally:
        for p in (tmp_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    return DUUIResponse(
        emotions=result["emotions"],
        model=result["model"],
    )