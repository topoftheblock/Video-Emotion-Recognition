# The video review viewer: FastAPI backend + static frontend. Reads
# Postgres and the video store; never parses CAS files itself, which is
# why its requirements.txt deliberately omits dkpro-cassis/lxml.
#
# Build context is the STACK ROOT (one level up), because this image
# needs shared/duui_parser/ as well as this directory:
#   docker build -f webapp/Dockerfile -t duui-webapp .
# ...which is exactly what webapp/build.sh does for you.
FROM python:3.12-slim

WORKDIR /app

COPY webapp/requirements.txt ./webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt

# Shared application code -- server.py imports duui_parser.config (for
# settings), duui_parser.db (connection handling) and
# duui_parser.query_agent (the NL->SQL "Ask" panel).
COPY shared/duui_parser ./duui_parser
COPY webapp/server.py ./webapp/server.py
COPY webapp/static ./webapp/static

ENV PYTHONUNBUFFERED=1

# Where it looks for video files -- must point at the same store the
# importer writes into (see README).
ENV DUUI_VIDEO_DIR=/data/videos

# Always 8000 inside the container; map it to whatever host port you
# like (compose defaults to 8010).
EXPOSE 8000

CMD ["uvicorn", "webapp.server:app", "--host", "0.0.0.0", "--port", "8000"]
