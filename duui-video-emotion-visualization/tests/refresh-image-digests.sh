#!/bin/sh
# Record which base images this project's builds are using.
#
#     tests/refresh-image-digests.sh
#
# Writes docker-images.lock at the project root. **Nothing reads that
# file.** The FROM lines stay on floating tags on purpose, so a rebuild
# keeps picking up security updates to the base; pinning by digest would
# freeze those permanently and silently. The file is a record you can
# diff, and reproduce from by hand if a rebuild ever misbehaves. It does
# not make the next build match it.
#
# Run it after a rebuild, or whenever you want to know what changed
# underneath. Two runs against unchanged images produce no diff.
set -e

cd "$(dirname "$0")/.."
OUT=docker-images.lock

# Every base this project pulls, in the order a build meets them. Kept
# in step with the FROM lines and the COPY --from by hand: there are
# three, and parsing Dockerfiles to find them would be more machinery
# than the problem deserves.
IMAGES="python:3.14-slim pgvector/pgvector:pg18 node:24-trixie-slim"

{
  echo "# Base images this project builds on, and the digests the last"
  echo "# refresh saw. Written by tests/refresh-image-digests.sh."
  echo "#"
  echo "# NOTHING READS THIS FILE. The Dockerfiles use floating tags so"
  echo "# that security rebuilds of the base still arrive. This records"
  echo "# what a build used; it does not pin what the next one gets."
  echo ""
} > "$OUT"

for image in $IMAGES; do
  # A digest only exists once the image is local, and `COPY --from` can
  # leave one pulled by the builder but not tagged here.
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "pulling $image..." >&2
    docker pull -q "$image" >/dev/null
  fi
  digest=$(docker image inspect "$image" --format '{{index .RepoDigests 0}}')
  printf '%s\n  %s\n' "$image" "${digest#*@}" >> "$OUT"
done

echo "wrote $OUT" >&2
