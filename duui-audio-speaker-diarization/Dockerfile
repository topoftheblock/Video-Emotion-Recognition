# pyannote runs on CPU or GPU. This slim image is CPU-friendly; for GPU,
# swap to an nvidia/cuda base and install a CUDA-enabled torch wheel.
FROM python:3.10-slim

# System deps for audio decoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Co-locate the module with the Lua + typesystem it reads at runtime so the
# relative paths in the Python module resolve inside the image.
COPY src/main/python/duui_audio_speaker_diarization.py ./duui_audio_speaker_diarization.py
COPY src/main/lua/communication.lua ./communication.lua
COPY src/main/resources/typesystem.xml ./typesystem.xml

EXPOSE 9714

# HuggingFace token is REQUIRED (pyannote/speaker-diarization-3.1 is gated).
# Provide it at run time, never bake it into the image:
#   docker run -e HF_TOKEN=hf_xxx -p 9714:9714 <image>
# Optional overrides: DUUI_DIARIZATION_MODEL_NAME, DUUI_DIARIZATION_DEVICE.
ENV HF_TOKEN="" \
    HF_HOME=/app/.cache/huggingface

CMD ["uvicorn", "duui_audio_speaker_diarization:app", "--host", "0.0.0.0", "--port", "9714"]
