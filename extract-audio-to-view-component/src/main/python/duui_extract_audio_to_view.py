"""
DUUI Component: Audio Extraction from Video

A DUUI-compatible REST service that receives a video (as base64) from a CAS view,
extracts its audio track with ffmpeg, and returns the audio (as base64) to be
written into a target view by the Lua communication layer.

The service exposes the four endpoints DUUI expects:
  GET  /v1/communication_layer  - returns the Lua script that (de)serializes the CAS
  GET  /v1/typesystem           - returns the UIMA typesystem as XML
  GET  /v1/documentation        - returns annotator metadata (name, version, params)
  POST /v1/process              - does the actual audio extraction

View routing (which view the video is read from and which view the audio is
written to) is controlled entirely from the Java pipeline via .withView()
and .withTargetView(); this service only deals with the JSON payloads.

The component listens on port 9714 inside the container, as required by DUUI.
The system `ffmpeg` binary must be installed in the image (apt-get install ffmpeg);
the chosen output codec is inferred by ffmpeg from the output file extension.

Author: Nickolas Eickmann
"""

import base64
import logging
import tempfile
import json
from pathlib import Path
from typing import Optional

from cassis import load_typesystem
from fastapi import FastAPI, Response, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from ffmpeg import FFmpeg

# Project root resolved relative to this file (.../src), so resource and Lua
# files are found regardless of the current working directory at launch.
BASE = Path(__file__).resolve().parents[2]   # .../src


class Settings(BaseSettings):
    """Runtime configuration, populated from environment variables.

    Each field is read from an env var named with the configured prefix, e.g.
    `annotator_name` <- TTLAB_DUUI_EXTRACT_AUDIO_TO_VIEW_ANNOTATOR_NAME. The defaults
    below let the service start locally without any env vars set; in the Docker
    image the ENV values (injected at build time) override them.
    """
    annotator_name: str = "duui_extract_audio_to_view"
    annotator_version: str = "dev"
    log_level: str | None = None
    model_config = SettingsConfigDict(env_prefix="ttlab_duui_extract_audio_to_view_")


class DUUIRequest(BaseModel):
    """Schema of the JSON body sent by the Lua `serialize` function.

    Field names must stay in sync with the keys written in communication.lua.
    """
    video_base64: str               # the input video, base64-encoded
    mime_type: Optional[str] = None  # incoming MIME type; optional, not used here
    output_format: str = "wav"       # desired audio format (drives output extension)


class DUUIResponse(BaseModel):
    """Schema of the JSON body returned to the Lua `deserialize` function."""
    audio_base64: Optional[str]      # extracted audio, base64-encoded (None on failure)
    mime_type: Optional[str]         # MIME type of the extracted audio (e.g. "audio/wav")


class DUUIDocumentation(BaseModel):
    """Schema returned by the /v1/documentation endpoint.

    Describes the annotator to DUUI and to humans: its name and version, a short
    description, the parameters it accepts, and its implementation language.
    """
    annotator_name: str
    version: str
    implementation_lang: Optional[str] = None
    meta: Optional[dict] = None
    docker_container_id: Optional[str] = None
    parameters: Optional[dict] = None


# --- Service initialization -------------------------------------------------

settings = Settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Load the typesystem once at startup so /v1/typesystem can return it. This
# component does not create annotation types (it writes a Sofa to another view),
# so the typesystem is mostly a formality, but the endpoint must still respond.
with open(BASE / 'main/resources/dkpro-core-types.xml', 'rb') as f:
    typesystem = load_typesystem(f)

# Load the Lua communication layer once at startup so /v1/communication_layer
# can hand it to DUUI. DUUI runs this script to (de)serialize the CAS.
with open(BASE / 'main/lua/communication.lua', 'rb') as f:
    lua_communication_script = f.read().decode("utf-8")

app = FastAPI(title=settings.annotator_name, version=settings.annotator_version)


# --- DUUI endpoints ---------------------------------------------------------

@app.get("/v1/communication_layer", response_class=PlainTextResponse)
def get_communication_layer() -> str:
    """Return the Lua script DUUI uses to convert between CAS and JSON."""
    return lua_communication_script


@app.get("/v1/typesystem")
def get_typesystem() -> Response:
    """Return the UIMA typesystem as XML."""
    return Response(content=typesystem.to_xml().encode("utf-8"), media_type="application/xml")


@app.get("/v1/documentation")
def get_documentation() -> DUUIDocumentation:
    """Return human- and machine-readable metadata describing this annotator.

    DUUI (and tooling around it) can query this to learn what the component does
    and which parameters it accepts, without having to run it.
    """
    return DUUIDocumentation(
        annotator_name=settings.annotator_name,
        version=settings.annotator_version,
        implementation_lang="Python",
        meta={
            "description": (
                "Extracts the audio track from a video stored in the source "
                "view's Sofa and writes it into the target view's Sofa. The "
                "input format is auto-detected by ffmpeg; the output format is "
                "configurable."
            ),
        },
        parameters={
            "output_format": (
                "Audio format / file extension of the extracted audio "
                "(e.g. 'wav', 'mp3', 'flac'). Default: 'wav'."
            ),
        },
    )


@app.post("/v1/process")
async def post_process(request: Request) -> DUUIResponse:
    """Extract the audio track from the incoming video and return it.

    The body is read and parsed manually (rather than via FastAPI's automatic
    model binding) to be robust against the payload arriving double-encoded as a
    JSON string instead of a JSON object.
    """
    body = await request.body()
    data = json.loads(body)
    # If the body decoded into a string, it was double-encoded: decode once more
    # so we end up with the actual object before constructing the request model.
    if isinstance(data, str):
        data = json.loads(data)
    req = DUUIRequest(**data)

    audio_b64 = None
    out_mime = None
    try:
        # Decode the incoming video back into raw bytes.
        video_bytes = base64.b64decode(req.video_base64)

        # Work in a temp dir that is cleaned up automatically. ffmpeg operates on
        # files, so we write the video out, transcode, then read the audio back.
        with tempfile.TemporaryDirectory() as tmp:
            # The input is written with a generic name (no format-specific
            # extension): ffmpeg detects the container/codec from the file's
            # contents, so the input format never has to be declared.
            video_path = Path(tmp) / "input"
            audio_path = Path(tmp) / f"output.{req.output_format}"
            video_path.write_bytes(video_bytes)

            # No input codec is specified: ffmpeg auto-detects the input format
            # from the file contents. The output codec is inferred from the
            # output file extension (.wav -> pcm, .mp3 -> libmp3lame, etc.).
            # ac=1 downmixes to mono; ar=16000 resamples to 16 kHz.
            ffmpeg = (FFmpeg().option("y").input(str(video_path))
                      .output(str(audio_path), ac=1, ar=16000))
            ffmpeg.execute()

            # Read the produced audio back and base64-encode it for transport.
            audio_b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
            out_mime = f"audio/{req.output_format}"
    except Exception as ex:
        # On any failure, log the traceback and fall through to a response with
        # null fields. The Lua deserialize side checks for null and simply does
        # not write a Sofa in that case, leaving the target view empty.
        logger.exception(ex)

    return DUUIResponse(audio_base64=audio_b64, mime_type=out_mime)