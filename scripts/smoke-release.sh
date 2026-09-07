#!/bin/sh
set -eu
test "$#" -eq 2
source_sha=$1
output=$2
rm -f "$output/public-smoke.json"
case "$source_sha" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#source_sha}" -eq 40
test -n "$FILLABLE_INITIAL_EMAIL"
test -n "$FILLABLE_INITIAL_PASSWORD"
. "$(dirname "$0")/release-transport.sh"
export FILLABLE_PUBLIC_ORIGIN="http://$FILLABLE_DEPLOY_HOST:3200"
digest=$(jq -er --arg sha "$source_sha" 'select(.source_sha == $sha) | .sha256' "$output/artifact.json")
case "$digest" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#digest}" -eq 64
image=$(jq -er '.images.backend.id' "$output/manifest.json")
case "$image" in sha256:*) ;; *) exit 2 ;; esac
public_check() {
  docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true \
    --memory 256m --cpus 0.5 --pids-limit 64 --user "$(id -u):$(id -g)" \
    -e PYTHONDONTWRITEBYTECODE=1 -e FILLABLE_PUBLIC_ORIGIN \
    -e FILLABLE_INITIAL_EMAIL -e FILLABLE_INITIAL_PASSWORD \
    -v "$PWD/scripts:/checks:ro" -v "$PWD/fixtures:/fixtures:ro" \
    -v "$output:/evidence" "$image" \
    python /checks/public_release_smoke.py "$1" "$source_sha" /evidence/public-smoke.json
}
result=0
public_check login || result=$?
if test "$result" -eq 3; then
  jq -n '{email:env.FILLABLE_INITIAL_EMAIL,password:env.FILLABLE_INITIAL_PASSWORD}' |
    remote "provision $source_sha $digest" > "$credentials/provision.json" || {
      printf 'initial_account_provision_failed\n' >&2; exit 1;
    }
  jq -e --arg sha "$source_sha" '.source_sha == $sha and .provisioned == true' "$credentials/provision.json" >/dev/null
  rm "$credentials/provision.json"
elif test "$result" -ne 0; then
  exit "$result"
fi
public_check smoke
printf 'Authenticated public release smoke passed for %s\n' "$source_sha"
