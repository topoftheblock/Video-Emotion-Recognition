# One-off cross-video identity job: clears every global person identity
# in the database and recomputes them from the face/voice embeddings
# already imported. Not a server -- it runs, does the work, and exits.
#
# Never runs on its own: it is corpus-wide, so when it runs is a
# decision, not a side effect of importing a file. Compose keeps it out
# of `up` behind a profile (see docker-compose.yml):
#   docker compose run --rm global-identity-linker
#
# Build context is THIS directory: everything the image needs lives in
# global-identity-linker/, nothing is pulled in from
# elsewhere in the stack.
#   docker build -t duui-video-emotion-visualization/global-identity-linker global-identity-linker/
FROM python:3.14-slim

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

# Not root. A container running as root does not fail loudly; it silently does
# more than it should -- and in this project it already cost an assertion, since
# a test that expects a permission error cannot get one as root (see
# docs/plan/phase-4-tooling.md). uid 1000 matches the other images.
# This job writes nothing to disk at all -- the database is its whole input and
# output -- so it needs no directory prepared.
RUN useradd --create-home --uid 1000 runner
USER runner

ENTRYPOINT ["python", "-m", "identity"]
