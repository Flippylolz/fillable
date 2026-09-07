#!/bin/sh
# Build a reviewed previous source and the Git index against one synthetic data set.
set -eu
verification_root=$(mktemp -d "${TMPDIR:-/tmp}/fillable-recovery.XXXXXX")
verification_project=$(basename "$verification_root" | tr '[:upper:].' '[:lower:]-')
verification_reports="${FILLABLE_RECOVERY_REPORTS:-$verification_root/reports}"
verification_baseline=191282ce485d6f562be0cd8d0a8b183b7e2ebb1d
verification_head=$(git rev-parse HEAD)
mkdir -p "$verification_root/previous" "$verification_root/current" "$verification_reports"
git cat-file -e "$verification_baseline^{commit}"
git archive "$verification_baseline" | tar -x -C "$verification_root/previous"
git checkout-index --all --prefix="$verification_root/current/"
cp "$verification_root/current/.env.example" "$verification_root/current/.env"
cp "$verification_root/previous/.env.example" "$verification_root/previous/.env"
export FILLABLE_PUBLIC_ORIGIN=http://gateway:8080 FILLABLE_UPSTREAM_PORT=0
export DOCUMENTS_HOST_PATH="$verification_root/documents"
export RECOVERY_PROOF_NONCE="$verification_project"
old() { docker compose --project-directory "$verification_root/previous" -p "$verification_project" -f "$verification_root/previous/compose.yaml" -f "$verification_root/previous/compose.prod.yaml" "$@"; }
current() { docker compose --project-directory "$verification_root/current" -p "$verification_project" -f "$verification_root/current/compose.yaml" -f "$verification_root/current/compose.prod.yaml" "$@"; }
browser() { docker compose --project-directory "$verification_root/current" -p "$verification_project" -f "$verification_root/current/compose.yaml" -f "$verification_root/current/compose.prod.yaml" -f "$verification_root/current/compose.browser.yaml" "$@"; }
cleanup() {
  current logs --no-color > "$verification_reports/runtime.log" 2>&1 || true
  current down >/dev/null 2>&1 || true
  echo "Recovery verification retained at $verification_root; project $verification_project; all volumes preserved."
}
trap cleanup EXIT
# A fresh unique namespace is mandatory; never attach to a retained prior proof.
test -z "$(docker volume ls -q --filter "label=com.docker.compose.project=$verification_project")"
test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$verification_project")"
install_probe() {
  "$1" exec -T api sh -c 'cat > /tmp/verify_application_recovery.py' < "$verification_root/current/scripts/verify_application_recovery.py"
  "$1" exec -T api sh -c 'cat > /tmp/recovery-source.docx' < "$verification_root/current/fixtures/docx/v1/client-intake-uk-v1.docx"
  "$1" exec -T api sh -c 'cat > /tmp/recovery-review.json' < "$verification_root/current/fixtures/docx/v1/working-review.json"
}
probe() { "$1" exec -T -e RECOVERY_PROOF_NONCE="$RECOVERY_PROOF_NONCE" api python /tmp/verify_application_recovery.py "$2"; }
badge() {
  mkdir -p "$verification_reports/$1"
  browser run --rm --no-deps --user "$(id -u):$(id -g)" -e HOME=/tmp -e EXPECTED_APP_VERSION="$2" -e PLAYWRIGHT_OUTPUT_DIR=/tmp/recovery-results/run -e PLAYWRIGHT_HTML_OUTPUT_DIR=/tmp/recovery-results/html --workdir /tmp -v "$verification_reports/$1:/tmp/recovery-results" browser /app/node_modules/.bin/playwright test --config /app/playwright.config.ts version-badge.spec.ts
}
export VITE_APP_COMMIT_SHA="$verification_baseline"
old up --build --wait --wait-timeout 120
old exec -T db psql -U fillable -d fillable -v ON_ERROR_STOP=1 -c "CREATE TABLE recovery_verification_guard (token text NOT NULL); INSERT INTO recovery_verification_guard VALUES ('$verification_project');"
test "$(old exec -T db psql -U fillable -d fillable -At -c 'SELECT version_num FROM alembic_version')" = 0012_audit_chronology
old exec -T api python -m app.accounts.cli provision --email upgrade-proof@example.test --display-name 'Синтетична перевірка Їжака' --language uk --password-stdin < "$verification_root/current/fixtures/auth/browser-password.txt"
install_probe old
probe old write > "$verification_reports/manifest.json"
probe old read < "$verification_reports/manifest.json"
browser build browser
badge previous "$(printf %s "$verification_baseline" | cut -c 1-7)"
old down
export VITE_APP_COMMIT_SHA="$verification_head"
current up --build --wait --wait-timeout 120
install_probe current
test "$(current exec -T db psql -U fillable -d fillable -At -c 'SELECT version_num FROM alembic_version')" = 0013_maintenance_state
probe current read < "$verification_reports/manifest.json"
current exec -T maintenance python /checks/verify_maintenance.py
badge upgraded "$(printf %s "$verification_head" | cut -c 1-7)"
# Stop only this synthetic project's scheduler while observing the crash boundary.
current stop maintenance
verification_run="$(current exec -T api python /checks/verify_maintenance.py identity)"
crash_exit=0
probe current crash || crash_exit=$?
test "$crash_exit" = 74
probe current pending < "$verification_reports/manifest.json"
current down
current up --wait --wait-timeout 120
install_probe current
current exec -T maintenance python /checks/verify_maintenance.py "$verification_run"
probe current read < "$verification_reports/manifest.json"
badge restarted "$(printf %s "$verification_head" | cut -c 1-7)"
echo 'PASS: previous-image upgrade, full-stack restart, reviewed/copy/restored DOCX history and real post-unlink crash reconciliation.'
