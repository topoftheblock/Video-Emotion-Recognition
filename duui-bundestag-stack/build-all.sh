#!/usr/bin/env bash
# Convenience: build all three images by calling each container's own
# build script. `docker compose build` does the same thing and tags the
# same names (compose's `image:` keys pin duui-db / duui-importer /
# duui-webapp); this is the compose-free path, for building without a
# compose file at all -- see README "Running without compose".
#
#   ./build-all.sh              -> all three at :latest
#   IMAGE_TAG=v2 ./build-all.sh -> all three at :v2 (each child script
#                                  inherits the variable)
#
# Note the summary at the end lists every duui-* image on the machine,
# not only the ones this run built.
set -euo pipefail

cd "$(dirname "$0")"

./db/build.sh
./importer/build.sh
./webapp/build.sh

echo
echo "All images built:"
docker images --filter "reference=duui-*" --format "  {{.Repository}}:{{.Tag}}  ({{.Size}})"
