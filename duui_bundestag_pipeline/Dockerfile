# CAS importer -- run one-off, not a long-running service:
#   docker compose run --rm importer python main.py cas/your_file.xmi
#
# Separate from webapp/Dockerfile because this needs dkpro-cassis/lxml
# (the full requirements.txt, not webapp/requirements.txt) to parse
# UIMA CAS XMI -- the webapp image deliberately excludes that
# dependency since server.py never imports the parser internals.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY duui_parser ./duui_parser
COPY main.py ./main.py

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "main.py"]
