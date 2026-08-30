# The identity linker: clears every global person and rebuilds them from
# the face and voice embeddings already in the database. Not a server —
# it runs, does the work, and exits.
#
# It never starts on its own. The work is corpus-wide, so running it is
# a decision rather than a side effect of importing a file, and a
# Compose profile keeps it out of `up`:
#
#   docker compose run --rm global-identity-linker
#
# The build context is this directory. Everything the image needs is
# inside global-identity-linker/; nothing is pulled in from the rest of
# the project.
FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# No `resources/` alongside it: unlike the importer, this job reads no
# typesystems and no CAS files, only the database.
COPY src ./src

ENV PYTHONUNBUFFERED=1
# `src` is the source root rather than a package, so putting it on the
# path is what makes `import identity` resolve here and in the tests.
ENV PYTHONPATH=/app/src

# Not root: a container running as root does not fail loudly, it
# silently does more than it should. This job writes nothing to disk —
# the database is its whole input and output — so no directory needs
# preparing first.
RUN useradd --create-home --uid 1000 runner
USER runner

# No arguments: the corpus already in the database is the entire input.
ENTRYPOINT ["python", "-m", "identity"]
