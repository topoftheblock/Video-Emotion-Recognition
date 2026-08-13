#!/usr/bin/env bash
# Build the webapp image on its own (no compose needed).
#
#   ./webapp/build.sh              -> tags duui-webapp:latest
#   IMAGE_TAG=v2 ./webapp/build.sh -> tags duui-webapp:v2
#
# Runs from the stack root on purpose: the build context has to include
# shared/duui_parser/, not just this directory.
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_NAME="${IMAGE_NAME:-duui-webapp}"

echo "Building ${IMAGE_NAME}:${IMAGE_TAG} (context: $(pwd)) ..."
docker build -f webapp/Dockerfile -t "${IMAGE_NAME}:${IMAGE_TAG}" .
echo "Done: ${IMAGE_NAME}:${IMAGE_TAG}"
