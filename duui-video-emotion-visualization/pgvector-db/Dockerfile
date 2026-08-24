# Postgres 16 + pgvector, with this project's schema baked in as an
# init script. Building our own thin image (instead of using
# pgvector/pgvector:pg18 directly plus a bind-mounted schema file)
# means the schema travels with the image -- so `docker run` of this
# image alone gives you a correctly-initialised database, with no
# "don't forget to mount schema.sql" step to get wrong.
#
# NOTE: /docker-entrypoint-initdb.d scripts run ONLY when the data
# directory is empty, i.e. on the very first start of a fresh volume.
# On an existing volume this file is ignored -- see README
# "Upgrading the schema on an existing database".
FROM pgvector/pgvector:pg18

COPY schema.sql /docker-entrypoint-initdb.d/01-schema.sql
