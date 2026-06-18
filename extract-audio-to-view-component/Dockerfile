FROM python:3.12-slim

WORKDIR /usr/src/app

# This port is required by the DUUI API
EXPOSE 9714

# Install ffmpeg (the actual binary, needed by the audio extraction)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir setuptools wheel
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Log level
ARG TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL="DEBUG"
ENV TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL=$TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL

# Meta data (annotator name + version, read by the Settings class)
ARG TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_NAME="duui-audio-extract"
ENV TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_NAME=$TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_NAME
ARG TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_VERSION="dev"
ENV TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_VERSION=$TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_VERSION

# Copy the needed scripts
COPY ./src/main/resources/dkpro-core-types.xml ./src/main/resources/dkpro-core-types.xml
COPY ./src/main/lua/communication.lua ./src/main/lua/communication.lua
COPY ./src/main/python/duui_extract_audio.py ./src/main/python/duui_extract_audio.py

# Start the server
ENTRYPOINT ["uvicorn", "src.main.python.duui_extract_audio:app", "--host", "0.0.0.0", "--port", "9714"]
CMD ["--workers", "1"]