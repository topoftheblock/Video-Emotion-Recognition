import json
from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import List
from collections import Counter

app = FastAPI(title="DUUI Audio Sentence Merger Engine")

with open("../lua/audio_sentence.lua", "r", encoding="utf-8") as f:
    lua_script = f.read()

class TokenData(BaseModel):
    begin: int
    end: int
    timeStart: float
    timeEnd: float
    speakerId: str

class SentenceData(BaseModel):
    begin: int
    end: int

class ProcessRequest(BaseModel):
    sentences: List[SentenceData]
    tokens: List[TokenData]

@app.get("/v1/communication_layer")
def get_lua():
    return Response(content=lua_script, media_type="text/plain")

@app.post("/v1/process")
def process(request: ProcessRequest):
    audio_sentences = []

    for sent in request.sentences:
        # Match tokens belonging to this sentence bound
        sent_tokens = [t for t in request.tokens if t.begin >= sent.begin and t.end <= sent.end]
        if not sent_tokens:
            continue

        time_start = min(t.timeStart for t in sent_tokens)
        time_end = max(t.timeEnd for t in sent_tokens)

        # Determine the primary speaker for this sentence (most common speaker among its words)
        speakers = [t.speakerId for t in sent_tokens if t.speakerId]
        assigned_speaker = "Unknown"
        if speakers:
            assigned_speaker = Counter(speakers).most_common(1)[0][0]

        audio_sentences.append({
            "begin": sent.begin,
            "end": sent.end,
            "timeStart": time_start,
            "timeEnd": time_end,
            "speakerId": assigned_speaker
        })

    return {"audio_sentences": audio_sentences}