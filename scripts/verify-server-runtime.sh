#!/bin/sh
set -eu
proof=$(mktemp -d)
export FILLABLE_BACKEND_IMAGE=sha256:0000000000000000000000000000000000000000000000000000000000000000
export FILLABLE_GATEWAY_IMAGE=sha256:1111111111111111111111111111111111111111111111111111111111111111
export FILLABLE_RUNTIME_ROOT=/fillable-runtime-proof/ops
export DOCUMENTS_HOST_PATH=/fillable-runtime-proof/documents
export FILLABLE_PUBLIC_ORIGIN=https://fillable.test:3200
export POSTGRES_PASSWORD=synthetic-runtime-proof-only
# Config generation is read-only: this does not start the production namespace.
docker compose -p fillable-production -f compose.yaml -f compose.prod.yaml -f compose.server.yaml config --format json > "$proof/compose.json"
printf '{"backend":{"id":"%s"},"gateway":{"id":"%s"}}\n' "$FILLABLE_BACKEND_IMAGE" "$FILLABLE_GATEWAY_IMAGE" > "$proof/images.json"
format=$(docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps -v "$PWD/scripts:/checks:ro" backend-test python -c 'import sys; sys.path.insert(0,"/checks"); from fillable_runtime import STATE_FORMAT; print(STATE_FORMAT)')
probe_id=$(docker create fillable-checks-backend-test true)
trap 'docker rm "$probe_id" >/dev/null' EXIT
docker inspect --format "$format" "$probe_id" > "$proof/no-health.json"
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps \
  --user "$(id -u):$(id -g)" -v "$PWD/scripts:/checks:ro" -v "$proof:/proof:ro" backend-test python /checks/verify_server_config.py /proof/compose.json /proof/images.json /proof/no-health.json
