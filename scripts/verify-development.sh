#!/bin/sh
# Verify the Git index in an isolated copy; never mutate the working checkout.
set -eu
verification_root=$(mktemp -d "${TMPDIR:-/tmp}/fillable-verify.XXXXXX")
verification_project="fillable-verify-$$"
verification_reports="${FILLABLE_BROWSER_REPORTS:-$verification_root/browser-results}"
mkdir -p "$verification_reports"
git checkout-index --all --prefix="$verification_root/"
cd "$verification_root"
cp .env.example .env
export FILLABLE_DEV_PORT=0 FILLABLE_UPSTREAM_PORT=0
export DOCUMENTS_HOST_PATH="$verification_root/var/storage"
dev() { docker compose -p "$verification_project" -f compose.yaml -f compose.dev.yaml "$@"; }
prod() { docker compose -p "$verification_project" -f compose.yaml -f compose.prod.yaml "$@"; }
cleanup() {
  dev logs --no-color > "$verification_root/runtime.log" 2>&1 || true
  dev down >/dev/null 2>&1 || true
  prod down >/dev/null 2>&1 || true
  echo "Verification copy retained at $verification_root; project $verification_project; volumes preserved."
}
trap cleanup EXIT

dev up --build --wait --wait-timeout 120
docker compose -p "$verification_project" -f compose.yaml -f compose.dev.yaml -f compose.browser.yaml build browser
docker compose -p "$verification_project" -f compose.yaml -f compose.dev.yaml -f compose.browser.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -e HOME=/tmp --workdir /tmp -v "$verification_reports:/tmp/fillable-dev-results" -v "$verification_root/frontend/src:/workspace/frontend" -v "$verification_root/backend/app:/workspace/backend" browser /app/node_modules/.bin/playwright test --config /app/playwright.dev.config.ts

dev exec -T db psql -U fillable -d fillable -v ON_ERROR_STOP=1 -c "CREATE TABLE development_probe (value text); INSERT INTO development_probe VALUES ('retained');"
dev exec -T redis redis-cli SET development_probe retained
dev down
prod up --build --wait --wait-timeout 120
test "$(prod exec -T db psql -U fillable -d fillable -At -c 'SELECT value FROM development_probe')" = retained
test "$(prod exec -T redis redis-cli GET development_probe)" = retained
prod exec -T db psql -U fillable -d fillable -v ON_ERROR_STOP=1 -c 'DROP TABLE development_probe'
prod exec -T redis redis-cli DEL development_probe
docker compose -p "$verification_project" -f compose.yaml -f compose.prod.yaml -f compose.browser.yaml run --rm --no-deps browser
prod exec -T gateway sh -c 'test "$(id -u)" != 0 && ! command -v node'
echo 'PASS: fresh staged checkout, hot reload, persistent recreation, production browser/static assets.'
