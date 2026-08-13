# One-off CAS importer: parses .xmi files into Postgres and copies each
# CAS's companion video into the shared video store. Not a server --
# it runs, does the work, and exits.
#
# Build context is THIS directory: everything the image needs lives in
# importer/, nothing is pulled in from elsewhere in the stack.
#   docker build -t duui-importer importer/
# ...which is exactly what importer/build.sh does for you.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Optional NLP enrichment (POS/NER backfill via spaCy). Uncomment both
# lines to bake it in, then run with DUUI_ENABLE_NLP_ENRICHMENT=true.
# Left out by default because it pulls in a ~13MB model download that
# most imports don't need -- see README "Post-processing".
# COPY requirements-nlp.txt ./requirements-nlp.txt
# RUN pip install --no-cache-dir -r requirements-nlp.txt

# The application code: the CAS parsers, the post-processing steps and
# the database layer.
COPY duui_parser ./duui_parser
COPY main.py ./main.py

# The three UIMA typesystem descriptors the parser needs to read a CAS.
# Baked in rather than mounted: they belong to the pipeline version this
# image was built for, so shipping them together keeps the two in sync.
# Override with DUUI_TS_* env vars + a mount if you need different ones.
COPY typesystems ./typesystems

ENV PYTHONUNBUFFERED=1

# Input and output defaults, both overridable at run time. These are
# container paths -- what you mount ONTO them is up to you (see README).
ENV DUUI_INPUT_DIR=/data/input
ENV DUUI_VIDEO_DIR=/data/videos

# Args are paths (files and/or directories); no args = import everything
# in DUUI_INPUT_DIR.
ENTRYPOINT ["python", "main.py"]
