# Postgres with pgvector, carrying this project's schema as an init
# script, so that running this image is enough to get an initialized
# database and there is no separate "remember to mount schema.sql" step.
#
# Scripts in /docker-entrypoint-initdb.d run only when the data
# directory is empty — the first start of a fresh volume. An existing
# volume ignores this file, so a schema change does not reach a database
# that already exists. See docs/operations.md.
FROM pgvector/pgvector:pg18

COPY schema.sql /docker-entrypoint-initdb.d/01-schema.sql
