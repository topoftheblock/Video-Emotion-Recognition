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

# Not root. A container running as root does not fail loudly; it silently does
# more than it should -- and in this project it already cost an assertion, since
# a test that expects a permission error cannot get one as root (see
# docs/plan/phase-4-tooling.md). uid 1000 matches the other images.
#
# create_app() calls VIDEO_DIR.mkdir(parents=True, exist_ok=True) before the
# mounts are registered. The store arrives read-only, so the directory must
# already exist and be owned by the runner or that call raises on a fresh volume.
RUN useradd --create-home --uid 1000 runner \
    && mkdir -p /data/videos \
    && chown -R runner:runner /data/videos
USER runner

EXPOSE 8000

# --factory because backend.app exposes create_app() rather than a
# module-level `app` -- see its docstring for why importing the package
# is kept free of side effects.
CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
