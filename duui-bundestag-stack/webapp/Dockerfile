# The video review viewer: FastAPI backend + static frontend. Reads
# Postgres and the video store; never parses CAS files itself, which is
# why its requirements.txt deliberately omits dkpro-cassis/lxml.
#
# Build context is THIS directory: everything the image needs lives in
# webapp/, nothing is pulled in from elsewhere in the stack.
#   docker build -t duui-webapp webapp/
# ...which is exactly what webapp/build.sh does for you.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The application code -- server.py imports duui_webapp.config (for
# settings), duui_webapp.db (connection handling) and
# duui_webapp.query_agent (the NL->SQL "Ask" panel).
COPY duui_webapp ./duui_webapp
COPY server.py ./server.py
COPY static ./static

ENV PYTHONUNBUFFERED=1

# Where it looks for video files -- must point at the same store the
# importer writes into (see README).
ENV DUUI_VIDEO_DIR=/data/videos

# Always 8000 inside the container; map it to whatever host port you
# like (compose defaults to 8010).
EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
