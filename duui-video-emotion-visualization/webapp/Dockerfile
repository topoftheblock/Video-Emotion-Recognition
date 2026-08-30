# The webapp: a FastAPI backend serving a static frontend. Reads
# Postgres and the video store, and never parses a CAS itself — which is
# why its requirements deliberately omit the UIMA and XML libraries.
#
# The build context is this directory. Everything the image needs is
# inside webapp/; nothing is pulled in from the rest of the project.
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The source root: the `backend` package and `frontend/`, the HTML, CSS
# and JavaScript the server mounts as static files. Copied verbatim, so
# the layout inside the image matches the repository exactly.
COPY src ./src

ENV PYTHONUNBUFFERED=1
# `src` is the source root rather than a package, so putting it on the
# path is what makes `import backend` resolve here and in the tests.
ENV PYTHONPATH=/app/src

# Where it looks for video files. Must point at the same store the
# importer writes into.
ENV DUUI_VIDEO_DIR=/data/videos

# Not root: a container running as root does not fail loudly, it
# silently does more than it should.
#
# `create_app` creates the video store before registering the mounts.
# The store arrives read-only, so the directory has to exist already and
# belong to the runner, or that call fails on a fresh volume.
RUN useradd --create-home --uid 1000 runner \
    && mkdir -p /data/videos \
    && chown -R runner:runner /data/videos
USER runner

# Always 8000 inside the container; Compose maps it to a host port.
EXPOSE 8000

# --factory because `backend.app` exposes `create_app` rather than a
# module-level app — see its docstring for why importing the package is
# kept free of side effects.
CMD ["uvicorn", "backend.app:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
