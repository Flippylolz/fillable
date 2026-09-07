#!/bin/sh
set -eu
test "$#" -eq 3
source_sha=$1
ci_run_id=$2
output=$3
case "$source_sha" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#source_sha}" -eq 40
case "$ci_run_id" in *[!0-9]*|'') exit 2 ;; esac
test "$ci_run_id" -gt 0
test "$(git rev-parse HEAD)" = "$source_sha"
git diff --quiet HEAD --
test ! -e "$output"
mkdir -m 700 "$output"
output=$(cd "$output" && pwd)
git archive --format=tar --output="$output/source.tar" "$source_sha"
mkdir "$output/context"
tar -xf "$output/source.tar" -C "$output/context"
backend="fillable-backend:$source_sha"
gateway="fillable-gateway:$source_sha"
docker build --platform linux/amd64 --label "org.opencontainers.image.revision=$source_sha" \
  -f "$output/context/infra/backend.Dockerfile" -t "$backend" "$output/context"
docker build --platform linux/amd64 --label "org.opencontainers.image.revision=$source_sha" \
  --build-arg "VITE_APP_COMMIT_SHA=$source_sha" --target gateway-prod \
  -f "$output/context/infra/frontend.Dockerfile" -t "$gateway" "$output/context"
format='{"id":"{{.Id}}","os":"{{.Os}}","architecture":"{{.Architecture}}","revision":"{{index .Config.Labels "org.opencontainers.image.revision"}}"}'
docker image inspect --format "$format" "$backend" > "$output/backend.json"
docker image inspect --format "$format" "$gateway" > "$output/gateway.json"
docker save --output "$output/images.tar" "$backend" "$gateway"
gzip -n "$output/images.tar" "$output/source.tar"
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$output/context/scripts:/checks:ro" -v "$output:/release" \
  python:3.13.12-slim-bookworm@sha256:a58daefb915e1e03ad48f3ca4df8832065412c5c35cacb9d39f4229184de12b6 \
  python /checks/release_artifact.py pack /release "$source_sha" "$ci_run_id"
