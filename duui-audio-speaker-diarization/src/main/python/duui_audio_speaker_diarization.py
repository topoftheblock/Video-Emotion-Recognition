"""DUUI Audio Speaker Diarization component.

Wraps pyannote.audio speaker diarization behind the DUUI component HTTP
contract. Receives base64-encoded audio in the request, runs diarization,
and returns the detected speaker turns (label + start/end in seconds).
The Lua communication layer turns those turns into SpeakerSegment
annotations in the CAS.
"""

import base64
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import torch
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pyannote.audio import Pipeline
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("duui-audio-speaker-diarization")

# Files that ship alongside this module inside the image.
_HERE = Path(__file__).resolve().parent
_LUA_PATH = _HERE / "communication.lua"
_TYPESYSTEM_PATH = _HERE / "typesystem.xml"


class Settings(BaseSettings):
    """Runtime configuration, populated from environment variables."""

    model_config = SettingsConfigDict(env_prefix="duui_diarization_")

    # HuggingFace access token. pyannote/speaker-diarization-3.1 is gated,
    # so this is required. Accept the common HF_TOKEN / HUGGINGFACE_TOKEN
    # names too for convenience.
    hf_token: Optional[str] = Field(default=None)
    model_name: str = "pyannote/speaker-diarization-3.1"
    # "cuda", "cpu", or None to auto-detect.
    device: Optional[str] = None

    def resolve_token(self) -> Optional[str]:
        return (
            self.hf_token
            or os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_TOKEN")
            or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        )

    def resolve_device(self) -> str:
        if self.device:
            return self.device
        return "cuda" if torch.cuda.is_available() else "cpu"


settings = Settings()


@lru_cache(maxsize=1)
def get_pipeline() -> Pipeline:
    """Load the diarization pipeline once and cache it.

    Loaded lazily on first request rather than at import time so the
    container can start (and report errors via HTTP) instead of crashing
    on boot when the token or weights are missing.
    """
    token = settings.resolve_token()
    if not token:
        raise RuntimeError(
            "No HuggingFace token configured. Set DUUI_DIARIZATION_HF_TOKEN "
            "or HF_TOKEN, and accept the user conditions for "
            f"'{settings.model_name}' on huggingface.co."
        )

    logger.info("Loading diarization model '%s'...", settings.model_name)
    pipeline = Pipeline.from_pretrained(settings.model_name, use_auth_token=token)
    if pipeline is None:
        # pyannote returns None instead of raising when access is denied.
        raise RuntimeError(
            f"Failed to load '{settings.model_name}'. The token may be invalid "
            "or the model conditions have not been accepted on HuggingFace."
        )

    device = settings.resolve_device()
    pipeline.to(torch.device(device))
    logger.info("Diarization model loaded on device '%s'.", device)
    return pipeline


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm the model on startup if a token is present, but never block
    # startup: failures are surfaced per-request instead.
    if settings.resolve_token():
        try:
            get_pipeline()
        except Exception:  # noqa: BLE001 - logged, not fatal at boot
            logger.exception("Model warm-up failed; will retry on first request.")
    else:
        logger.warning("No HuggingFace token set yet; model will load on first request.")
    yield


app = FastAPI(
    title="DUUI Audio Speaker Diarization",
    description="Speaker diarization (pyannote.audio) as a DUUI component.",
    version="1.0.0",
    lifespan=lifespan,
)


class DiarizationRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64-encoded audio (e.g. WAV).")
    num_speakers: Optional[int] = Field(
        default=None, description="Exact number of speakers, if known."
    )
    min_speakers: Optional[int] = Field(default=None)
    max_speakers: Optional[int] = Field(default=None)


class SpeakerTurn(BaseModel):
    speaker_id: str
    start: float
    end: float


class DiarizationResponse(BaseModel):
    segments: List[SpeakerTurn]


@app.get("/v1/communication_layer", response_class=PlainTextResponse)
def communication_layer() -> str:
    return _LUA_PATH.read_text(encoding="utf-8")


@app.get("/v1/typesystem")
def typesystem() -> Response:
    return Response(
        content=_TYPESYSTEM_PATH.read_text(encoding="utf-8"),
        media_type="application/xml",
    )


@app.get("/v1/documentation")
def documentation() -> dict:
    return {
        "name": "DUUI Audio Speaker Diarization",
        "version": app.version,
        "model": settings.model_name,
        "device": settings.resolve_device(),
        "description": "Runs pyannote.audio speaker diarization and returns "
        "speaker turns as SpeakerSegment annotations.",
    }


@app.post("/v1/process", response_model=DiarizationResponse)
def process(request: DiarizationRequest) -> DiarizationResponse:
    try:
        pipeline = get_pipeline()
    except RuntimeError as exc:
        # Configuration / auth problems -> 503, the request can be retried
        # once the container is configured correctly.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 audio.") from exc

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio payload.")

    # Unique temp file per request -> safe under parallel DUUI workers.
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.flush()
        tmp.close()

        diar_kwargs = {}
        if request.num_speakers is not None:
            diar_kwargs["num_speakers"] = request.num_speakers
        if request.min_speakers is not None:
            diar_kwargs["min_speakers"] = request.min_speakers
        if request.max_speakers is not None:
            diar_kwargs["max_speakers"] = request.max_speakers

        diarization = pipeline(tmp.name, **diar_kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Diarization failed.")
        raise HTTPException(status_code=500, detail=f"Diarization failed: {exc}") from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            logger.warning("Could not remove temp file %s", tmp.name)

    segments = [
        SpeakerTurn(speaker_id=speaker, start=float(turn.start), end=float(turn.end))
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    return DiarizationResponse(segments=segments)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9714)
