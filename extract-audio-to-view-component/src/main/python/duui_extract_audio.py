import base64
import logging
import tempfile
from pathlib import Path
from typing import Optional

from cassis import load_typesystem
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from ffmpeg import FFmpeg

BASE = Path(__file__).resolve().parents[2]   # .../src

class Settings(BaseSettings):
    annotator_name: str = "duui_extract_audio"
    annotator_version: str = "dev"
    log_level: str | None = None
    model_config = SettingsConfigDict(env_prefix="ttlab_duui_extract_audio_")


class DUUIRequest(BaseModel):
    video_base64: str
    mime_type: str
    input_format: str = "mp4"
    output_format: str = "wav"


class DUUIResponse(BaseModel):
    audio_base64: Optional[str]
    mime_type: Optional[str]


settings = Settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

with open(BASE / 'main/resources/dkpro-core-types.xml', 'rb') as f:
    typesystem = load_typesystem(f)

with open(BASE / 'main/lua/communication.lua', 'rb') as f:
    lua_communication_script = f.read().decode("utf-8")

app = FastAPI(title=settings.annotator_name, version=settings.annotator_version)


@app.get("/v1/communication_layer", response_class=PlainTextResponse)
def get_communication_layer() -> str:
    return lua_communication_script


@app.get("/v1/typesystem")
def get_typesystem() -> Response:
    return Response(content=typesystem.to_xml().encode("utf-8"), media_type="application/xml")


@app.post("/v1/process")
def post_process(request: DUUIRequest) -> DUUIResponse:
    audio_b64 = None
    out_mime = None

    try:
        video_bytes = base64.b64decode(request.video_base64)

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / f"input.{request.input_format}"
            audio_path = Path(tmp) / f"output.{request.output_format}"
            video_path.write_bytes(video_bytes)

            ffmpeg = (
                FFmpeg()
                .option("y")
                .input(str(video_path))
                .output(str(audio_path), acodec="pcm_s16le", ac=1, ar=16000)
            )
            ffmpeg.execute()

            #subprocess.run(
             #   ["ffmpeg", "-y", "-i", str(video_path),
              #   "-vn", str(audio_path)],
               # check=True, capture_output=True,
            #)

            audio_bytes = audio_path.read_bytes()
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            out_mime = f"audio/{request.output_format}"

    except Exception as ex:
        logger.exception(ex)

    return DUUIResponse(audio_base64=audio_b64, mime_type=out_mime)