# One-off cross-video identity job: clears every global person identity
# in the database and recomputes them from the face/voice embeddings
# already imported. Not a server -- it runs, does the work, and exits.
#
# Never runs on its own: it is corpus-wide, so when it runs is a
# decision, not a side effect of importing a file. Compose keeps it out
# of `up` behind a profile (see docker-compose.yml):
#   docker compose run --rm global-identity
#
# Build context is THIS directory: everything the image needs lives in
# duui-video-emotion-global-identity/, nothing is pulled in from
# elsewhere in the stack.
#   docker build -t duui-video-emotion-global-identity duui-video-emotion-global-identity/
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# The whole source root: the `identity` package (matching logic, entry
# module, database layer). No `resources/` here -- unlike the importer,
# this job reads no typesystems and no CAS files, only the database.
COPY src ./src

ENV PYTHONUNBUFFERED=1
# `src` is the source root, not a package -- putting it on the path is
# what makes `import identity` resolve, here and in the test suite.
ENV PYTHONPATH=/app/src

# Takes no arguments: the corpus in the database is the entire input.
ENTRYPOINT ["python", "-m", "identity"]
