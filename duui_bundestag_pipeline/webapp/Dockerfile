# Build from the repo root:
#   docker build -f webapp/Dockerfile -t duui-webapp .
# (needs the root as build context because it also copies duui_parser/,
# which server.py imports for DB access and the query agent.)

FROM python:3.12-slim

WORKDIR /app

COPY webapp/requirements.txt ./webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt

# Only what server.py actually imports: config, db, query_agent.
# The parser-only modules (pipeline.py, typesystem.py, parsers/) come
# along too since they're cheap files with no import-time side effect
# unless something explicitly imports them -- server.py never does.
COPY duui_parser ./duui_parser
COPY webapp ./webapp

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "webapp.server:app", "--host", "0.0.0.0", "--port", "8000"]
