#!/bin/sh
# Shared private SSH setup; source from release delivery/check scripts.
test -n "$FILLABLE_DEPLOY_HOST"
test -n "$FILLABLE_DEPLOY_USER"
test -n "$FILLABLE_DEPLOY_KEY"
test -n "$FILLABLE_KNOWN_HOSTS"
umask 077
credentials=$(mktemp -d)
trap 'rm -f "$credentials/key" "$credentials/known_hosts" "$credentials/provision.json"; rmdir "$credentials"' EXIT
trap 'exit 1' HUP INT TERM
printf '%s\n' "$FILLABLE_DEPLOY_KEY" > "$credentials/key"
printf '%s\n' "$FILLABLE_KNOWN_HOSTS" > "$credentials/known_hosts"
remote() {
  ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes \
    -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -o "UserKnownHostsFile=$credentials/known_hosts" -i "$credentials/key" \
    -- "$FILLABLE_DEPLOY_USER@$FILLABLE_DEPLOY_HOST" "$@" 2>/dev/null
}
