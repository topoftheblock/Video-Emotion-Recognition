# DUUI Extract Audio To View

A [DUUI](https://github.com/texttechnologylab/DockerUnifiedUIMAInterface) component that extracts the audio track from a video view and writes it into a separate view.

The video is read (as a base64 string) from a source view's Sofa, its audio is extracted with `ffmpeg`, and the resulting audio is written (again as base64) into a target view's Sofa. Which views are used is controlled entirely from the Java pipeline, so the component itself stays reusable.

**Author:** Nickolas Eickmann

## How it works

The component is a FastAPI service that uses the DUUI component contract. A request flows through three layers:

1. **Java pipeline** picks the source/target views and the output format and calls the component.
2. **Lua communication layer** (`communication.lua`) reads the video Sofa out of the source view, sends it to the Python service as JSON, then writes the returned audio into the target view's Sofa.
3. **Python service** (`duui_extract_audio_to_view.py`) receives the video bytes, runs `ffmpeg`, and returns the extracted audio.

The input format is **auto-detected** by `ffmpeg` from the video view , so it never has to be declared. Only the desired output format is configurable.

## REST API

The service listens on port `9714` (required by DUUI) and exposes the standard DUUI endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/v1/communication_layer` | Returns the Lua script that (de)serializes the CAS |
| `GET` | `/v1/typesystem` | Returns the UIMA typesystem as XML |
| `GET` | `/v1/documentation` | Returns annotator metadata (name, version, parameters) |
| `POST` | `/v1/process` | Extracts the audio and returns it |

## Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `output_format` | `wav` | Audio format / file extension of the extracted audio (e.g. `wav`, `mp3`, `flac`). The output codec is inferred by `ffmpeg` from this extension. |

The extracted audio is downmixed to mono and resampled to 16 kHz.

## Build

```bash
docker build -t duui_extract_audio_to_view .
```

The image installs the system `ffmpeg` binary (required for the actual extraction) and the Python dependencies from `requirements.txt`.

Build-time arguments can override the defaults baked into the image, for example:

```bash
docker build \
  --build-arg TTLAB_DUUI_EXTRACT_AUDIO_TO_VIEW_ANNOTATOR_VERSION=1.0.0 \
  -t duui_extract_audio_to_view:1.0.0 .
```

## Run

Standalone (for testing the service directly):

```bash
docker run --rm -p 9714:9714 duui_extract_audio_to_view
```

Then verify it responds:

```bash
curl http://localhost:9714/v1/documentation
```

## Use in a DUUI pipeline

Add the component to a composer, choosing the source view (containing the video) and the target view (which will receive the audio):

```java
composer.add(new DUUIDockerDriver.Component("duui_extract_audio_to_view")
        .withView("_InitialView")
        .withTargetView("audioView")
        .withParameter("output_format", "wav"));
```

The target view is created and populated with the extracted audio's Sofa. The audio Sofa is stored as a base64 string tagged with the appropriate MIME type (e.g. `audio/wav`).

## Configuration

Runtime settings are read from environment variables with the prefix `ttlab_duui_extract_audio_to_view_`:

| Environment variable | Default | Description |
| --- | --- | --- |
| `TTLAB_DUUI_EXTRACT_AUDIO_TO_VIEW_ANNOTATOR_NAME` | `duui_extract_audio_to_view` | Annotator name reported by the service |
| `TTLAB_DUUI_EXTRACT_AUDIO_TO_VIEW_ANNOTATOR_VERSION` | `dev` | Annotator version |
| `TTLAB_DUUI_EXTRACT_AUDIO_TO_VIEW_LOG_LEVEL` | `DEBUG` | Python logging level |

## Project structure

```
.
├── Dockerfile
├── requirements.txt
└── src
    ├── main
    │   ├── lua/communication.lua              # CAS <-> JSON (de)serialization
    │   ├── python/duui_extract_audio_to_view.py  # the FastAPI service
    │   └── resources/dkpro-core-types.xml     # UIMA typesystem
    └── test
        ├── python/decodeAudioBase64.py        # extract & decode audio from an output XMI
        └── resources/dkpro-core-types.xml
```

## Testing the output

After running a pipeline that ends with an XMI writer, the extracted audio is embedded in the output XMI as the target view's Sofa. `src/test/python/decodeAudioBase64.py` pulls that Sofa out, decodes the base64, auto-detects the audio format from its magic bytes, and writes a playable file:

```bash
cd src/test/python
python decodeAudioBase64.py
```

Adjust `XMI_PATH`, `VIEW_NAME`, and `OUT_DIR` at the top of the script to match your output.

## Requirements

- Docker (for building and running the component)
- `ffmpeg` — installed automatically inside the image; required on the host only if running the Python service outside Docker
- Python dependencies are pinned in `requirements.txt` (FastAPI, uvicorn, pydantic v2, dkpro-cassis, python-ffmpeg, lxml)