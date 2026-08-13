#!/usr/bin/env bash
# Build the database image on its own (no compose needed).
#
#   ./db/build.sh              -> tags duui-db:latest
#   IMAGE_TAG=v2 ./db/build.sh -> tags duui-db:v2
#
# Build context is this directory: the image only needs schema.sql.
set -euo pipefail

cd "$(dirname "$0")"

IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_NAME="${IMAGE_NAME:-duui-db}"

echo "Building ${IMAGE_NAME}:${IMAGE_TAG} ..."
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
echo "Done: ${IMAGE_NAME}:${IMAGE_TAG}"
