#!/usr/bin/env bash
# Convenience: build all three images by calling each container's own
# build script. Equivalent to `docker compose build`, but produces
# plainly-named images (duui-db / duui-importer / duui-webapp) you can
# also run without compose -- see README "Running without compose".
set -euo pipefail

cd "$(dirname "$0")"

./db/build.sh
./importer/build.sh
./webapp/build.sh

echo
echo "All images built:"
docker images --filter "reference=duui-*" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"
