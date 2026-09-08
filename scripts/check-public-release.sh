#!/bin/sh
# Actions readiness needs no account credential or SSH key.
set -eu
test "$#" -eq 2
source_sha=$1
output=$2
rm -f "$output/public-readiness.json"
case "$source_sha" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#source_sha}" -eq 40
export FILLABLE_PUBLIC_ORIGIN="https://$FILLABLE_DEPLOY_HOST:3200"
jq -e --arg sha "$source_sha" '.source_sha == $sha and .status == "succeeded"' "$output/deployment.json" >/dev/null
image=$(jq -er --arg sha "$source_sha" 'select(.source_sha == $sha and .images.backend.revision == $sha) | .images.backend.id' "$output/manifest.json")
printf '%s' "$image" | grep -Eq '^sha256:[0-9a-f]{64}$'
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true \
  --memory 256m --cpus 0.5 --pids-limit 64 --user "$(id -u):$(id -g)" \
  -e PYTHONDONTWRITEBYTECODE=1 -e FILLABLE_PUBLIC_ORIGIN \
  -v "$PWD/scripts:/checks:ro" -v "$output:/evidence" "$image" \
  python /checks/public_release_readiness.py "$source_sha" /evidence/public-readiness.json || {
    rm -f "$output/public-readiness.json"; exit 1;
  }
jq -e --arg sha "$source_sha" '.source_sha == $sha and .status == "succeeded" and .authenticated_acceptance == "pending"' "$output/public-readiness.json" >/dev/null || {
  rm -f "$output/public-readiness.json"; exit 1;
}
printf 'Public readiness passed for %s; private authenticated acceptance pending\n' "$source_sha"
