# The video review viewer: FastAPI backend + static frontend. Reads
# Postgres and the video store; never parses CAS files itself, which is
# why its requirements.txt deliberately omits dkpro-cassis/lxml.
#
# Build context is THIS directory: everything the image needs lives in
# webapp/, nothing is pulled in from
# elsewhere in the stack.
#   docker build -t duui-video-emotion-visualization/webapp webapp/
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The whole source root: the `backend` package (settings, DB layer, the
# NL->SQL "Ask" agent) plus `frontend/` -- the HTML/CSS/JS the server
# mounts as static files. Copied verbatim so the layout inside the
# image matches the repo exactly.
COPY src ./src

ENV PYTHONUNBUFFERED=1
# `src` is the source root, not a package -- putting it on the path is
# what makes `import backend` resolve, here and in the test suite.
ENV PYTHONPATH=/app/src

# Where it looks for video files -- must point at the same store the
# importer writes into (see README).
ENV DUUI_VIDEO_DIR=/data/videos

# Always 8000 inside the container; map it to whatever host port you
# like (compose defaults to 8010).
EXPOSE 8000

# --factory because backend.app exposes create_app() rather than a
# module-level `app` -- see its docstring for why importing the package
# is kept free of side effects.
CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
