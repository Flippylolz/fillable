#!/bin/sh
# The destination key is restricted to the separately prepared Fillable receiver.
set -eu
test "$#" -eq 2
source_sha=$1
output=$2
case "$source_sha" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#source_sha}" -eq 40
test -n "$FILLABLE_DEPLOY_HOST"
test -n "$FILLABLE_DEPLOY_USER"
test -n "$FILLABLE_DEPLOY_KEY"
test -n "$FILLABLE_KNOWN_HOSTS"
umask 077
credentials=$(mktemp -d)
trap 'rm -f "$credentials/key" "$credentials/known_hosts"; rmdir "$credentials"' EXIT
trap 'exit 1' HUP INT TERM
printf '%s\n' "$FILLABLE_DEPLOY_KEY" > "$credentials/key"
printf '%s\n' "$FILLABLE_KNOWN_HOSTS" > "$credentials/known_hosts"
digest=$(jq -er --arg sha "$source_sha" 'select(.source_sha == $sha) | .sha256' "$output/artifact.json")
case "$digest" in *[!0-9a-f]*|'') exit 2 ;; esac
test "${#digest}" -eq 64
# A receiver absence/configuration error fails before upload or rollout. SSH stderr
# can contain private connection identity; keep it out of published workflow logs.
remote() {
  ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes \
    -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -o "UserKnownHostsFile=$credentials/known_hosts" -i "$credentials/key" \
    -- "$FILLABLE_DEPLOY_USER@$FILLABLE_DEPLOY_HOST" "$@" 2>/dev/null
}
remote check > "$output/receiver-check.json" || { printf 'release_receiver_unavailable\n' >&2; exit 1; }
jq -e '.protocol == 1 and .ready == true' "$output/receiver-check.json" >/dev/null
remote "receive $source_sha $digest" < "$output/release.tar" > "$output/receiver-upload.json" || { printf 'release_upload_failed\n' >&2; exit 1; }
jq -e --arg sha "$source_sha" --arg digest "$digest" \
  '.source_sha == $sha and .sha256 == $digest and .verified == true' "$output/receiver-upload.json" >/dev/null
remote "apply $source_sha $digest" > "$output/receiver-apply.json" || { printf 'release_apply_failed\n' >&2; exit 1; }
jq -e --arg sha "$source_sha" '.source_sha == $sha and .status == "succeeded"' "$output/receiver-apply.json" >/dev/null
# Construct the public record from validated local values; never upload raw remote output.
jq -n --arg sha "$source_sha" --arg digest "$digest" \
  '{source_sha:$sha, sha256:$digest, status:"succeeded"}' > "$output/deployment.json"
printf 'Release applied and verified for %s\n' "$source_sha"
