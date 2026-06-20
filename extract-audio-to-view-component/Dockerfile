# ============================================================================
# DUUI Component: Audio Extraction from Video
#
# Builds the container image for the audio-extraction annotator. The image runs
# a FastAPI/uvicorn service that DUUI talks to over HTTP. Besides the Python
# dependencies, it installs the system `ffmpeg` binary, which does the actual
# audio extraction (the python-ffmpeg package only wraps the binary, it does not
# bundle it).
# ============================================================================

# Slim Python base: small image, Debian-based so `apt-get` is available for
# installing ffmpeg below. Python 3.12 matches the version used in development.
FROM python:3.12-slim

# All subsequent paths (COPY targets, the uvicorn module path) are relative to
# this working directory inside the container.
WORKDIR /usr/src/app

# DUUI expects every component to serve on port 9714; expose it so the driver
# can map and reach the service.
EXPOSE 9714

# Install ffmpeg (the actual binary, needed by the audio extraction).
# --no-install-recommends keeps the image small; removing the apt lists
# afterwards avoids shipping the package index in the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies.
# setuptools/wheel are installed first so that source-only packages can build.
# requirements.txt is copied on its own before the app code so this layer is
# cached and only re-runs when the dependencies actually change.
RUN pip install --no-cache-dir setuptools wheel
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Log level.
# ARG = build-time overridable (docker build --build-arg ...); ENV = present at
# runtime. The Python Settings class reads TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL.
ARG TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL="DEBUG"
ENV TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL=$TTLAB_DUUI_EXTRACT_AUDIO_LOG_LEVEL

# Meta data (annotator name + version, read by the Settings class).
# These map to settings.annotator_name / settings.annotator_version via the
# env_prefix "ttlab_duui_extract_audio_". Bump the version per release.
ARG TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_NAME="duui-audio-extract"
ENV TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_NAME=$TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_NAME
ARG TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_VERSION="dev"
ENV TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_VERSION=$TTLAB_DUUI_EXTRACT_AUDIO_ANNOTATOR_VERSION

# Copy the needed scripts.
# Only the three runtime files are copied (typesystem, Lua layer, app). The in-container
# paths mirror the repo layout because the Python code resolves them relative to
# its own location (Path(__file__).parents[2]).
COPY ./src/main/resources/dkpro-core-types.xml ./src/main/resources/dkpro-core-types.xml
COPY ./src/main/lua/communication.lua ./src/main/lua/communication.lua
COPY ./src/main/python/duui_extract_audio.py ./src/main/python/duui_extract_audio.py

# Start the server.
# ENTRYPOINT launches uvicorn pointing at the FastAPI `app` object; --host
# 0.0.0.0 makes it reachable from outside the container (not just localhost),
# and --port 9714 is the DUUI-required port. CMD supplies default extra args
# that can be overridden at `docker run` time without replacing the entrypoint.
ENTRYPOINT ["uvicorn", "src.main.python.duui_extract_audio:app", "--host", "0.0.0.0", "--port", "9714"]
CMD ["--workers", "1"]