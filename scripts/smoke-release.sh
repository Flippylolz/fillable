#!/bin/sh
# Private operator acceptance only: never provision or reset accounts here.
set -eu
test "$#" -eq 2
source_sha=$1
output=$2
rm -f "$output/public-smoke.json"
case "$source_sha" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#source_sha}" -eq 40
test -n "$FILLABLE_PUBLIC_ORIGIN"
test -n "$FILLABLE_INITIAL_LOGIN"
test -n "$FILLABLE_INITIAL_PASSWORD"
jq -e --arg sha "$source_sha" '.source_sha == $sha and .status == "succeeded"' "$output/deployment.json" >/dev/null
image=$(jq -er --arg sha "$source_sha" 'select(.source_sha == $sha and .images.backend.revision == $sha) | .images.backend.id' "$output/manifest.json")
printf '%s' "$image" | grep -Eq '^sha256:[0-9a-f]{64}$'
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 256m --cpus 0.5 --pids-limit 64 --user "$(id -u):$(id -g)" \
  -e PYTHONDONTWRITEBYTECODE=1 -e FILLABLE_PUBLIC_ORIGIN \
  -e FILLABLE_INITIAL_LOGIN -e FILLABLE_INITIAL_PASSWORD \
  -v "$PWD/scripts:/checks:ro" -v "$PWD/fixtures:/fixtures:ro" \
  -v "$output:/evidence" "$image" \
  python /checks/public_release_smoke.py smoke "$source_sha" /evidence/public-smoke.json || {
    rm -f "$output/public-smoke.json"; exit 1;
  }
jq -e --arg sha "$source_sha" '.source_sha == $sha and .status == "succeeded" and .versions_verified == 2' "$output/public-smoke.json" >/dev/null || {
  rm -f "$output/public-smoke.json"; exit 1;
}
printf 'Authenticated private release smoke passed for %s\n' "$source_sha"
