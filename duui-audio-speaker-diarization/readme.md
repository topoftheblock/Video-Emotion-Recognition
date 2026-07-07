# DUUI Audio Speaker Diarization

Speaker diarization ("who spoke when") as a [DUUI](https://github.com/texttechnologylab/DockerUnifiedUIMAInterface)
component, wrapping [pyannote.audio](https://github.com/pyannote/pyannote-audio).

The component reads base64-encoded audio from a CAS view, runs the
`pyannote/speaker-diarization-3.1` pipeline, and writes one
`org.texttechnologylab.annotation.audio.SpeakerSegment` per detected speaker
turn, each carrying `speakerId`, `timeStart`, and `timeEnd` (seconds).

## Requirements

`pyannote/speaker-diarization-3.1` is **gated**. Before use you must:

1. Create a HuggingFace account and a read token.
2. Accept the user conditions for the model on its HuggingFace page.

## Build & run

```bash
docker build -t duui-audio-speaker-diarization .
docker run -e HF_TOKEN=hf_xxx -p 9714:9714 duui-audio-speaker-diarization
```

### Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `HF_TOKEN` (or `DUUI_DIARIZATION_HF_TOKEN`) | yes | HuggingFace access token. |
| `DUUI_DIARIZATION_MODEL_NAME` | no | Override the pyannote model. |
| `DUUI_DIARIZATION_DEVICE` | no | `cuda` or `cpu`. Auto-detected if unset. |

## Endpoints

- `GET  /v1/communication_layer` — Lua serialize/deserialize script.
- `GET  /v1/typesystem` — the `SpeakerSegment` type this component produces.
- `GET  /v1/documentation` — component metadata.
- `POST /v1/process` — `{ "audio_base64": "..." }` → `{ "segments": [...] }`.

Optional `process` parameters: `num_speakers`, `min_speakers`, `max_speakers`.

## Component parameters (Lua)

- `audio_view` — name of the view holding the audio SOFA (default `audio`).
- `target_view` — view to write `SpeakerSegment` annotations into (default: base view).
- `num_speakers` / `min_speakers` / `max_speakers` — forwarded as diarization hints.

## Note on offsets

`SpeakerSegment` annotations use begin/end character offsets of `0`; they are
anchored on the audio timeline through `timeStart`/`timeEnd`. A downstream merge
step (e.g. a sentence aligner) is responsible for mapping these onto transcript
spans by temporal overlap.
