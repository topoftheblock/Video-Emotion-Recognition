# One-off CAS importer: parses .xmi files into Postgres and copies each
# CAS's companion video into the shared video store. Not a server --
# it runs, does the work, and exits.
#
# Build context is THIS directory: everything the image needs lives in
# cas-to-postgres-importer/, nothing is pulled in from
# elsewhere in the stack.
#   docker build -t duui-video-emotion-visualization/cas-to-postgres-importer cas-to-postgres-importer/
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The whole source root: the `importer` package (CAS parsers,
# post-processing, entry module, database layer) plus `resources/` --
# which carries the three UIMA typesystem descriptors the parser needs
# to read a CAS. Those are baked in rather than mounted: they belong to
# the pipeline version this image was built for, so shipping them
# together keeps the two in sync. Override with DUUI_TS_* env vars + a
# mount if you need different ones.
COPY src ./src

ENV PYTHONUNBUFFERED=1
# `src` is the source root, not a package -- putting it on the path is
# what makes `import importer` resolve, here and in the test suite.
ENV PYTHONPATH=/app/src

# Input and output defaults, both overridable at run time. These are
# container paths -- what you mount ONTO them is up to you (see README).
ENV DUUI_INPUT_XMI_DIR=/data/input/xmi
ENV DUUI_INPUT_VIDEO_DIR=/data/input/videos
ENV DUUI_VIDEO_DIR=/data/videos

# Args are paths (files and/or directories); no args = import everything
# in DUUI_INPUT_XMI_DIR.
ENTRYPOINT ["python", "-m", "importer"]
