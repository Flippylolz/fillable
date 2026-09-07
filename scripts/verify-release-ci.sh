#!/bin/sh
set -eu
test "$#" -eq 1
docker run --rm \
  -e GH_TOKEN -e GITHUB_REPOSITORY -e GITHUB_REF -e GITHUB_SHA -e GITHUB_EVENT_NAME \
  -v "$PWD/scripts:/checks:ro" \
  python:3.13.12-slim-bookworm@sha256:a58daefb915e1e03ad48f3ca4df8832065412c5c35cacb9d39f4229184de12b6 \
  python /checks/release_gate.py "$1"
