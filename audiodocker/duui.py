import base64
import io
import logging
from pathlib import Path
from platform import python_version
from sys import version as sys_version
from tempfile import TemporaryDirectory
from time import time
from typing import List, Optional

import torch
from cassis import *
from fastapi import FastAPI, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from starlette.responses import JSONResponse
from transformers import pipeline

class EmotionToken(BaseModel):
    emotion: str
    confidence: float

class AnnotationMeta(BaseModel):
    name: str
    version: str
    modelName: str
    modelVersion: str

class DocumentModification(BaseModel):
    user: str
    timestamp: int
    comment: str

class DUUIRequest(BaseModel):
    audio: str  # audio in base64

class DUUIResponse(BaseModel):
    emotions: List[EmotionToken]
    meta: Optional[AnnotationMeta]
    modification_meta: Optional[DocumentModification]

class DUUICapability(BaseModel):
    supported_languages: List[str]
    reproducible: bool

class DUUIDocumentation(BaseModel):
    annotator_name: str
    version: str
    implementation_lang: Optional[str]
    meta: Optional[dict]
    docker_container_id: Optional[str]
    parameters: Optional[dict]
    capability: DUUICapability
    implementation_specific: Optional[str]

class Settings(BaseSettings):
    annotator_name: str
    annotator_version: str
    log_level: str

    class Config:
        env_prefix = 'duui_whisper_ser_'

settings = Settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

logger.info("Initializing Fine-Tuned Whisper Model...")
device = 0 if torch.cuda.is_available() else -1
classifier = pipeline(
    task="audio-classification", 
    model="firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3",
    device=device
)
logger.info("Model loaded.")

with open("src/main/lua/duui.lua", "rb") as f:
    communication = f.read().decode("utf-8")

with open("src/main/resources/TypeSystem.xml", 'rb') as f:
    typesystem = load_typesystem(f)
    typesystem_xml_content = typesystem.to_xml().encode("utf-8")

app = FastAPI(
    docs_url="/api",
    redoc_url=None,
    title=settings.annotator_name,
    description="Fine-Tuned Whisper SER DUUI",
    version=settings.annotator_version,
)

@app.get("/v1/details/input_output")
def get_input_output() -> JSONResponse:
    json_item = {
        "inputs": [],
        "outputs": ["org.texttechnologylab.annotation.emotion.Emotion"]
    }
    return JSONResponse(content=jsonable_encoder(json_item))

@app.get("/v1/typesystem")
def get_typesystem() -> Response:
    return Response(content=typesystem_xml_content, media_type="application/xml")

@app.get("/v1/communication_layer", response_class=PlainTextResponse)
def get_communication_layer() -> str:
    return communication

@app.get("/v1/documentation")
def get_documentation() -> DUUIDocumentation:
    return DUUIDocumentation(
        annotator_name=settings.annotator_name,
        version=settings.annotator_version,
        implementation_lang="Python",
        meta={"python_version": python_version()},
        docker_container_id="",
        parameters={},
        capability=DUUICapability(supported_languages=["EN"], reproducible=True),
        implementation_specific=None,
    )

@app.post("/v1/process")
def post_process(request: DUUIRequest) -> DUUIResponse:
    start_time = int(time())
    
    with TemporaryDirectory() as audio_dir:
        audio_file = Path(audio_dir) / "audio.wav"
        with open(audio_file, "wb") as fp:
            fp.write(base64.b64decode(request.audio))
            
        results = classifier(str(audio_file))
        
        emotions = [
            EmotionToken(emotion=emo['label'], confidence=emo['score'])
            for emo in results
        ]

    meta = AnnotationMeta(
        name=settings.annotator_name,
        version=settings.annotator_version,
        modelName="firdhokk/speech-emotion-recognition-with-openai-whisper-large-v3",
        modelVersion="latest"
    )

    modification_meta = DocumentModification(
        user=settings.annotator_name,
        timestamp=start_time,
        comment=f"{settings.annotator_name} ({settings.annotator_version})"
    )

    return DUUIResponse(
        emotions=emotions,
        meta=meta,
        modification_meta=modification_meta
    )
