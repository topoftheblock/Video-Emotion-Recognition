import json
from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import List

app = FastAPI(title="DUUI Audio Sentence Merger Engine")

with open("audio_sentence.lua", "r", encoding="utf-8") as f:
    lua_script = f.read()

class TokenData(BaseModel):
    begin: int
    end: int
    timeStart: float
    timeEnd: float

class SentenceData(BaseModel):
    begin: int
    end: int

class SpeakerData(BaseModel):
    speakerId: str
    timeStart: float
    timeEnd: float

class ProcessRequest(BaseModel):
    sentences: List[SentenceData]
    tokens: List[TokenData]
    speakers: List[SpeakerData]

@app.get("/v1/communication_layer")
def get_lua():
    return Response(content=lua_script, media_type="text/plain")

@app.post("/v1/process")
def process(request: ProcessRequest):
    audio_sentences = []

    for sent in request.sentences:
        # Match tokens belonging to this sentence bound
        sent_tokens = [t for token in request.tokens if token.begin >= sent.begin and token.end <= sent.end]
        if not sent_tokens:
            continue

        time_start = min(t.timeStart for t in sent_tokens)
        time_end = max(t.timeEnd for t in sent_tokens)

        # Resolve speaker via majority temporal overlap
        assigned_speaker = "Unknown"
        max_overlap = 0.0
        for spk in request.speakers:
            overlap_start = max(time_start, spk.timeStart)
            overlap_end = min(time_end, spk.timeEnd)
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > max_overlap:
                max_overlap = overlap
                assigned_speaker = spk.speakerId

        audio_sentences.append({
            "begin": sent.begin,
            "end": sent.end,
            "timeStart": time_start,
            "timeEnd": time_end,
            "speakerId": assigned_speaker
        })

    return {"audio_sentences": audio_sentences}