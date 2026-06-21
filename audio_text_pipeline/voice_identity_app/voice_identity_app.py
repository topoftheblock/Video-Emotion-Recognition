import base64
import json
from pyannote.audio import Pipeline
from fastapi import FastAPI, Response
from pydantic import BaseModel

app = FastAPI(title="DUUI Voice Identity Engine")
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token="YOUR_HF_TOKEN")

with open("voice_identity.lua", "r", encoding="utf-8") as f:
    lua_script = f.read()

class ProcessRequest(BaseModel):
    audio_base64: str

@app.get("/v1/communication_layer")
def get_lua():
    return Response(content=lua_script, media_type="text/plain")

@app.post("/v1/process")
def process(request: ProcessRequest):
    audio_data = base64.b64decode(request.audio_base64)
    with open("temp_diar.wav", "wb") as f:
        f.write(audio_data)

    diarization = pipeline("temp_diar.wav")
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append({
            "speaker_id": speaker,
            "start": turn.start,
            "end": turn.end
        })
    return {"segments": segments}