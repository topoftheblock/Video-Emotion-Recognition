#!/usr/bin/env bash
# Build the importer image on its own (no compose needed).
#
#   ./importer/build.sh              -> tags duui-importer:latest
#   IMAGE_TAG=v2 ./importer/build.sh -> tags duui-importer:v2
#
# Build context is this directory: the image needs nothing from outside
# importer/.
set -euo pipefail

cd "$(dirname "$0")"

IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_NAME="${IMAGE_NAME:-duui-importer}"

echo "Building ${IMAGE_NAME}:${IMAGE_TAG} (context: $(pwd)) ..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
echo "Done: ${IMAGE_NAME}:${IMAGE_TAG}"
