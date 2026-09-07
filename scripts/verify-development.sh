#!/bin/sh
# Verify the Git index in an isolated copy; never mutate the working checkout.
set -eu
verification_root=$(mktemp -d "${TMPDIR:-/tmp}/fillable-verify.XXXXXX")
verification_project="fillable-verify-$$"
verification_reports="${FILLABLE_BROWSER_REPORTS:-$verification_root/browser-results}"
mkdir -p "$verification_reports/production"
git checkout-index --all --prefix="$verification_root/"
cd "$verification_root"
cp .env.example .env
export FILLABLE_DEV_PORT=0 FILLABLE_UPSTREAM_PORT=0
export FILLABLE_PUBLIC_ORIGIN=http://gateway:8080
export DOCUMENTS_HOST_PATH="$verification_root/var/storage"
dev() { docker compose -p "$verification_project" -f compose.yaml -f compose.dev.yaml -f compose.editor-proof.yaml "$@"; }
prod() { docker compose -p "$verification_project" -f compose.yaml -f compose.prod.yaml "$@"; }
cleanup() {
  dev logs --no-color > "$verification_root/runtime.log" 2>&1 || true
  dev down >/dev/null 2>&1 || true
  prod down >/dev/null 2>&1 || true
  echo "Verification copy retained at $verification_root; project $verification_project; volumes preserved."
}
trap cleanup EXIT

dev up --build --wait --wait-timeout 120
dev exec -T api python /checks/verify_gateway_logs.py probe development
dev logs --no-color --no-log-prefix gateway > "$verification_root/gateway-dev.log"
dev exec -T api python /checks/verify_gateway_logs.py check development < "$verification_root/gateway-dev.log"
# Explicit synthetic fixture only; normal startup never provisions an account.
dev exec -T api python -m app.accounts.cli provision --email browser@example.test --display-name "Тестовий користувач" --language en --password-stdin < fixtures/auth/browser-password.txt
dev exec -T api python -m app.accounts.cli provision --email profile@example.test --display-name "Тест профілю" --language uk --password-stdin < fixtures/auth/browser-password.txt
dev exec -T api python -m app.accounts.cli provision --email library@example.test --display-name "Тест бібліотеки" --language uk --password-stdin < fixtures/auth/browser-password.txt
dev exec -T api python -m app.accounts.cli provision --email review@example.test --display-name "Перевірка полів" --language uk --password-stdin < fixtures/auth/browser-password.txt
dev exec -T api python -m app.accounts.cli provision --email lease-desktop@example.test --display-name "Перевірка доступу" --language uk --password-stdin < fixtures/auth/browser-password.txt
dev exec -T api python -m app.accounts.cli provision --email lease-mobile@example.test --display-name "Перевірка доступу" --language uk --password-stdin < fixtures/auth/browser-password.txt
dev exec -T api python /checks/verify_storage_persistence.py write
dev exec -T api python /checks/verify_document_persistence.py write < fixtures/docx/v1/client-intake-uk-v1.docx
dev exec -T api python /checks/verify_processing.py
dev exec -T worker python /checks/verify_storage_persistence.py read
dev exec -T worker python -m app.storage.quota_cli default --bytes 1048576
dev exec -T worker python -m app.storage.quota_cli override --email browser@example.test --bytes 0
dev exec -T worker python /checks/verify_storage_persistence.py quota-zero
dev exec -T worker python -m app.storage.quota_cli inherit --email browser@example.test
dev exec -T worker python -m app.storage.quota_cli default --bytes 1073741824
dev exec -T worker python -m app.storage.quota_cli show --email browser@example.test
docker compose -p "$verification_project" -f compose.yaml -f compose.dev.yaml -f compose.browser.yaml build browser
docker compose -p "$verification_project" -f compose.yaml -f compose.dev.yaml -f compose.browser.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -e HOME=/tmp --workdir /tmp -v "$verification_reports:/tmp/fillable-dev-results" -v "$verification_root/frontend/src:/workspace/frontend" -v "$verification_root/backend/app:/workspace/backend" browser /app/node_modules/.bin/playwright test --config /app/playwright.dev.config.ts

dev exec -T db psql -U fillable -d fillable -v ON_ERROR_STOP=1 -c "CREATE TABLE development_probe (value text); INSERT INTO development_probe VALUES ('retained');"
dev exec -T redis redis-cli SET development_probe retained
dev exec -T api python -m app.documents.retention_cli set --keep-latest 2
dev down
prod up --build --wait --wait-timeout 120
prod exec -T api python /checks/verify_gateway_logs.py probe
prod logs --no-color --no-log-prefix gateway > "$verification_root/gateway-prod.log"
prod exec -T api python /checks/verify_gateway_logs.py check < "$verification_root/gateway-prod.log"
test "$(prod exec -T db psql -U fillable -d fillable -At -c 'SELECT value FROM development_probe')" = retained
test "$(prod exec -T redis redis-cli GET development_probe)" = retained
prod exec -T db psql -U fillable -d fillable -v ON_ERROR_STOP=1 -c 'DROP TABLE development_probe'
prod exec -T redis redis-cli DEL development_probe
prod exec -T api python /checks/verify_storage_persistence.py read
prod exec -T worker python /checks/verify_storage_persistence.py read
prod exec -T api python /checks/verify_document_persistence.py read < fixtures/docx/v1/client-intake-uk-v1.docx
prod exec -T api python /checks/verify_processing.py
prod exec -T -e FILLABLE_PUBLIC_ORIGIN="$FILLABLE_PUBLIC_ORIGIN" worker python /checks/verify_document_persistence.py read < fixtures/docx/v1/client-intake-uk-v1.docx
prod exec -T worker python -m app.storage.maintenance reconcile
prod exec -T worker python -m app.storage.maintenance inventory
prod exec -T worker python -m app.storage.maintenance capacity
prod exec -T worker python -m app.documents.retention_cli show
prod exec -T api python -m app.diagnostics status
prod exec -T api python -m app.diagnostics audit --limit 2
docker compose -p "$verification_project" -f compose.yaml -f compose.prod.yaml -f compose.browser.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -e HOME=/tmp -e PLAYWRIGHT_OUTPUT_DIR=/tmp/fillable-prod-results/run -e PLAYWRIGHT_HTML_OUTPUT_DIR=/tmp/fillable-prod-results/html --workdir /tmp -v "$verification_reports/production:/tmp/fillable-prod-results" browser /app/node_modules/.bin/playwright test --config /app/playwright.config.ts
prod exec -T worker python -m app.documents.retention_cli set --keep-latest all
prod exec -T gateway sh -c 'test "$(id -u)" != 0 && ! command -v node'
echo 'PASS: fresh staged checkout, hot reload, persistent recreation, production browser/static assets.'
