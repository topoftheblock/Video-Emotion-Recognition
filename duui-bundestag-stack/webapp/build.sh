#!/usr/bin/env bash
# Build the webapp image on its own (no compose needed).
#
#   ./webapp/build.sh              -> tags duui-webapp:latest
#   IMAGE_TAG=v2 ./webapp/build.sh -> tags duui-webapp:v2
#
# Build context is this directory: the image needs nothing from outside
# webapp/.
set -euo pipefail

cd "$(dirname "$0")"

IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_NAME="${IMAGE_NAME:-duui-webapp}"

echo "Building ${IMAGE_NAME}:${IMAGE_TAG} (context: $(pwd)) ..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
echo "Done: ${IMAGE_NAME}:${IMAGE_TAG}"
