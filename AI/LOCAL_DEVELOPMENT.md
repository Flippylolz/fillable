# Docker development and verification

The four-page application is implemented: login, library, profile and document
workspace with field review, synchronized editing, autosave and version history.
Development and production-style checks run through pinned Docker images. Live
server access and deployment belong to E08, after the remaining operational audit.
See [Epics](EPICS.md) for verified task and PR evidence.

## Requirements and startup

Install Git and Docker with Compose and use a POSIX shell. Host Node, Python,
PostgreSQL, Redis and browser installations are not required. From the repository:

```sh
test -f .env || cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build --wait --wait-timeout 120
```

Open `http://localhost:8180`. Ukrainian is the initial UI language; the profile
supports persisted English as well. Normal startup creates no accounts. Provision
an account with the interactive password prompt:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec api python -m app.accounts.cli provision --login owner --display-name 'Власник документів' --language uk
```

Use your intended account identifier and a password of at least 10 characters.
For explicit automation, the same command accepts `--password-stdin`; do not put
passwords in command arguments. [Authentication](AUTHENTICATION.md) covers account
management. The synthetic fixture accounts are created only by verification scripts.

```sh
docker compose -f compose.yaml -f compose.dev.yaml down
```

Ordinary shutdown preserves PostgreSQL/Redis volumes and the document bind mount.
Never add `-v`, delete volumes, or prune the host to troubleshoot startup. Inspect
this project's logs and fix its failing dependency or configuration.

## Services, isolation and bounds

| Service | Purpose | Memory / CPU limit |
| --- | --- | --- |
| `gateway` | Non-root nginx; Vite proxy in development, static assets in production | 128 MiB / 0.5 |
| `web` | Development-only Vite, with source/index mounts | 768 MiB / 1 |
| `api` | Non-root FastAPI, account/document/save APIs; development reload | 512 MiB / 1 |
| `db` | Private PostgreSQL 18.3 and retained volume | 512 MiB / 1 |
| `redis` | Private Redis 8.6.1, append-only transport state | 256 MiB / 0.5 |
| `worker` | One Python RQ worker, revision-fenced deterministic discovery | 512 MiB / 1 |
| `dispatcher` | Bounded PostgreSQL outbox dispatch and expired-job recovery | 256 MiB / 0.5 |
| `maintenance` | Bounded reconciliation and explicitly configured retention | 256 MiB / 0.5 |
| `migrate` | One-shot reviewed Alembic migrations | 256 MiB / 0.5 |
| `storage-init` | One-shot ownership of the dedicated document root | 128 MiB / 0.5 |

These are container ceilings, not a measured minimum host requirement. Build/test
and Playwright tooling are separate. All runtime services use scoped `json-file`
rotation of 10 MB per file and three files per container; no Docker daemon setting
or shared nginx configuration is changed. Production has no Node runtime.

Only the gateway publishes a loopback port. PostgreSQL and Redis remain private.
Compose owns its namespaced resources; shared server ingress is outside its lifecycle.
API, worker and maintenance share only the configured document mount. Worker,
dispatcher, maintenance and one-shot services have read-only roots and writable
`/tmp`; production API and both gateways do too. Development API/web source mounts
are read-only from the container; edit source in the checkout.

Startup waits for storage initialization and successful migrations. `/api/ready`
checks the exact migration heads and Redis; `/api/health` checks process responsiveness.
Worker payloads are JSON with opaque IDs and job-description logging disabled.
[Diagnostics](DIAGNOSTICS.md) and [Maintenance](MAINTENANCE.md) explain status,
counters, audit events, retries and scheduler progress.

## Configuration and retained data

`.env.example` is for local defaults. Preserve an existing `.env`; never commit
runtime secrets. Production needs a distinct private database password. Compose
constructs its database URL, so the password must be URL-safe; E08 validates the
actual private configuration before deployment.

| Setting | Use |
| --- | --- |
| `COMPOSE_PROJECT_NAME` | Local namespace; explicit `-p` takes precedence |
| `FILLABLE_PUBLIC_ORIGIN` | Exact origin, including port, for cookies/CSRF |
| `FILLABLE_DEV_PORT` | Loopback development port, default 8180; 0 requests an ephemeral port |
| `FILLABLE_UPSTREAM_PORT` | Loopback production-style port, default 8181; live allocation is E08 |
| `DOCUMENTS_HOST_PATH` | Dedicated retained host directory, default `./var/storage` |
| `POSTGRES_PASSWORD` | Private database credential; example is local-only |
| `STORAGE_FILE_BYTES` | Upload/storage default maximum, 10 MiB |
| `STORAGE_STAGING_BYTES` | Shared active staging allowance, default 64 MiB |
| `STORAGE_DISK_HEADROOM_BYTES` | Required physical headroom, default 64 MiB |
| `STORAGE_LEASE_SECONDS` | Storage operation lease, default 60 seconds |
| `MAINTENANCE_BATCH` | Entries per maintenance task, default 20; range 1–100 |
| `MAINTENANCE_INTERVAL_SECONDS` | Cooldown after a tick, default 60; range 10–3600 |

API and worker operations use the same quota service for every retained write.
Originals, independent copies and retained revisions consume their actual bytes.
`storage-init` changes ownership only for the dedicated root and immediate managed
directories, never recursively through another application's files. Give local and
production real data separate directories and namespaces; changing `-p` alone does
not change a configured bind path. Read [Storage quotas](STORAGE_QUOTAS.md).

History retention is all revisions by default. Only explicit operator policy enables
pruning; reduced quotas do not authorize deletion. Temporary file staging remains
crash-recoverable storage. The excluded “staging” is a persistent deployment
environment. Backups are outside MVP; retained history is not disk-loss recovery.

## Source changes and contracts

Uvicorn reloads mounted Python and Vite reflects frontend source/index edits. Worker,
dispatcher and maintenance code changes require a scoped rebuild/recreation.
Dependencies, generated clients and configuration also require image rebuilds.

```sh
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml logs --tail 30 api worker maintenance
```

Versions and image digests are pinned in `infra/`, Compose and lockfiles. Update
backend dependencies with Docker and pinned `pip-tools==7.5.3`; use
`pip-compile --generate-hashes`. Update frontend dependencies with the pinned Node
image and `npm install --save-exact`. Commit locks and rebuild.

After API schema changes, generate both artifacts through Docker:

```sh
docker compose -p fillable-checks -f compose.test.yaml build
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/generated:/output" backend-test python /checks/export_openapi.py /output/openapi.json
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/generated:/app/generated" frontend-test npm run generate:api
```

No live database is needed for generation. Rebuild afterward. CI rejects generated
schema/type drift; authored client behavior stays in covered `frontend/src`.

## Required test and coverage checks

Use the explicit isolated test namespace. Do not run backend suites/probes concurrently
against the same test database. The fixtures refuse an application database.

```sh
docker compose -p fillable-checks -f compose.test.yaml build
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps backend-test sh -c 'ruff check . && mypy app'
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps frontend-test sh -c 'npm run lint && npm run check:i18n && npm run build'
docker compose -p fillable-checks -f compose.test.yaml run --rm backend-test
report_container="fillable-frontend-report-$(date +%s)-$$"
docker compose -p fillable-checks -f compose.test.yaml run --name "$report_container" frontend-test
mkdir -p frontend/coverage
docker cp "$report_container:/app/coverage/." frontend/coverage/
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps -v "$PWD/frontend:/source:ro" backend-test python /checks/check_coverage.py frontend /source
```

Lints and tests run in separate fast steps against the same pinned images: Ruff
and mypy for the backend, ESLint, catalog/copy checks and the TypeScript build
for the frontend. The test services run real backend integration tests and raw
coverage gates, and Vitest coverage for the frontend. Both independently need
at least 90% lines and branches, including unimported application files and
authored migrations. Tests discard old reports; the named frontend container
retains its new reports. The gate contract test mounts the checked-out workflow
so it validates the actual `ci-required` job list:

```sh
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps \
  -v "$PWD/.github/workflows/ci.yml:/checks/ci.yml:ro" \
  backend-test python /checks/test_gate_contract.py
```

[CI and deployment](CI_CD.md) documents negative probes, required jobs and
gates.

## Fresh installation, browser flows and recovery

Stage intended changes, then run these direct commands:

```sh
scripts/verify-development.sh
scripts/verify-application-recovery.sh
```

Each driver captures a Git tree from the index and executes its staged script from
an immutable temporary launcher. Unstaged edits and ignored secrets are excluded;
later source/index edits cannot change the running verification. Each run uses a
fresh, collision-checked project name and ephemeral loopback ports. It retains all
volumes and prints the temporary evidence path after stopping its own services.

The development driver checks actual runtime memory/CPU limits, log rotation,
non-root users, writable mounts, loopback isolation and absence of OOM/container
restarts before and after the representative flows. It records point-in-time Docker
memory/CPU samples; these are not peak measurements. It verifies frontend HMR,
backend reload, marker persistence, production recreation, operator commands,
scheduler progress and all desktop/mobile application browser cases. Test accounts
and synthetic documents are provisioned explicitly inside that isolated project.

The [application recovery proof](APPLICATION_RECOVERY.md) builds the pinned previous
application, upgrades the same isolated database/files to current images, verifies
edited/copy/restored history and proves actual post-unlink crash reconciliation.
Both CI jobs must pass. The main job additionally runs
`scripts/verify-docx-render.sh <BROWSER_REPORT_DIRECTORY>` for independent rendering.
Read [Editor feasibility](EDITOR_FEASIBILITY.md) and [Test corpus](TEST_CORPUS.md)
for the supported structural-editing limits; this is not a Microsoft Word execution test.

For the isolated editor prototype only, the explicit `compose.editor-proof.yaml`
override exposes the synthetic corpus API. It is used by development verification
and must never be included in production. Normal production runs the authenticated
application without that endpoint.
