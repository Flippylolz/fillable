# Docker development and deployment

Status: implementation specification for E01. Compose files, Dockerfiles, and the commands below are not implemented yet.

Local Docker setup and CI are early foundation work. Deployment to `<DEPLOY_USER>@<DEPLOY_HOST>` is exclusively final epic E08, orchestrated by GitHub Actions. See [CI and deployment](CI_CD.md) for ordering/coverage gates and [Deployment target](DEPLOYMENT_TARGET.md) for shared nginx, possible WEF ownership, and isolation requirements.

## Required developer experience

The host needs Git and Docker with Docker Compose. All language runtimes, dependencies, migrations, workers, and test tools run in containers. Use Docker Desktop on development platforms that need it, or Docker Engine with the Compose plugin on Linux.

A fresh checkout should need only a local environment file and one documented Compose startup command. Provide safe development defaults and an idempotent local setup process.

## Planned services

| Service | Development | Production |
| --- | --- | --- |
| `gateway` | Project-owned nginx routes browser requests and Vite hot-reload traffic | Serves built assets and proxies API behind shared nginx on a new private upstream port |
| Shared nginx | Not needed on the developer host | Existing server-managed HTTP listener on Fillable's new public port; outside Fillable Compose lifecycle |
| `web` | Containerized Node/Vite with source reload | No runtime service; frontend is built into static assets |
| `api` | Python/FastAPI with source reload | Python/FastAPI application server |
| `worker` | Python/RQ; reload or restart on source changes | Python/RQ workers |
| `db` | PostgreSQL with persistent volume | PostgreSQL with persistent volume |
| `redis` | Redis with local persistence | Redis with local persistence |
| `migrate` | One-shot Alembic migration service | Explicit migration step before application startup |
| test profile | Python, frontend, and browser-test containers | Used in CI, not production runtime |

An editor-specific service can be added only after D008 verifies free licensing and compatibility with the no-Node-backend constraint. Keep editor-independent startup usable until then. Do not add AI services or provider credentials to MVP.

## Configuration structure

- `compose.yaml`: shared services, networks, volumes, and health checks.
- `compose.dev.yaml`: source mounts or Compose Watch, development commands, project-owned nginx routing, test profile.
- `compose.prod.yaml`: production image targets, routing, restart policy, and resource configuration.
- `.env.example`: safe examples and explanations. Never put secrets or real documents into Git.
- Runtime and image versions must be pinned during E01; do not rely on floating `latest` tags.
- Container dependency directories must not be copied from the host. Dependency changes rebuild the relevant image.

Expected command contract, to be implemented and verified in E01:

```sh
cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build
docker compose -f compose.yaml -f compose.dev.yaml down
```

Migrations must complete before dependent services accept requests. Health checks distinguish a running process from a ready database or API. Ordinary shutdown must preserve volumes; data-reset commands must be separate and explicitly destructive.

References: [Compose startup readiness](https://docs.docker.com/compose/how-tos/startup-order/), [Compose Watch](https://docs.docker.com/compose/how-tos/file-watch/).

## Local data

- PostgreSQL and Redis state use persistent local volumes. Shared nginx and existing TLS state remain managed by the current server configuration owner.
- Local and production use separate data/configuration. CI stacks are disposable, not a persistent staging environment. No backup services, snapshot tasks, or backup/restore commands are part of MVP.
- Document files use a configurable host directory mounted into API and worker containers at the same container storage root.
- Suggested development host directory: `./var/storage`, ignored by Git. Production uses an operator-selected server directory.
- Staging and final document files share a filesystem when atomic rename is used.
- Run application processes as non-root, with a documented solution for mount ownership on supported developer platforms.
- Do not publish PostgreSQL or Redis ports by default. Optional diagnostic access binds only to localhost.
- Give Fillable its own Compose project namespace. In local development, publish the gateway on a configurable local port. In production, shared nginx listens on `FILLABLE_PUBLIC_PORT`; the gateway remains private at `FILLABLE_UPSTREAM_PORT` or on the existing private ingress network. Do not reserve host ports 80/443. Choose networking after inspecting shared nginx; use loopback for the upstream when nginx is host-native.

## Configuration contract

E01 and E02 will implement and document these settings; they are names for the planned contract, not existing environment variables.

| Setting | Purpose |
| --- | --- |
| `DOCUMENTS_HOST_PATH` | Host directory mounted as document storage |
| `STORAGE_ROOT` | Container path used by the storage service |
| `FILLABLE_DEV_PORT` | Configurable gateway port for local development |
| `FILLABLE_PUBLIC_PORT` | New public shared-nginx HTTP listener, verified unused during E08 |
| `FILLABLE_UPSTREAM_PORT` | Separate private gateway host port when required by shared-nginx networking |
| `APP_PUBLIC_URL` | Exact browser origin including scheme and port; production is `http://<DEPLOY_HOST>:<PORT>` |
| `SESSION_COOKIE_SECURE` | False for the explicitly configured HTTP origin; true for an HTTPS origin. Validate against `APP_PUBLIC_URL` rather than guessing from untrusted forwarded headers |
| `COMPOSE_PROJECT_NAME` | Isolated project namespace, checked against existing server projects before deployment |
| `DEFAULT_USER_QUOTA_BYTES` | Initial global default allowance; subsequently administrator-managed |
| `MAX_UPLOAD_BYTES` | Maximum compressed input file size |
| `MAX_DOCX_EXPANDED_BYTES` | Maximum total expanded DOCX size |
| `MAX_DOCX_ENTRIES` | Maximum ZIP entry count |
| `TEMP_STORAGE_LIMIT_BYTES` | Separate global temporary-processing allowance |
| `MIN_FREE_DISK_BYTES` | Free-space floor for each filesystem used by processing |
| `STORAGE_RESERVATION_TTL_SECONDS` | Lease interval for active write reservations |
| `DATABASE_URL` / `REDIS_URL` | Private service connection configuration |
| `SESSION_SECRET` | Authentication secret, supplied outside Git |

The quota default setting bootstraps database configuration once; restarting containers must not overwrite an administrator's later changes. Numeric example values are deployment defaults, not limits embedded in code.

E02 supplies containerized operator commands for account provisioning, credential reset, the global quota default, and per-user overrides. These commands use the application's validation and audit services. They keep administration available without adding a fifth MVP page or requiring direct database edits.

## E01 verification

- Compose configuration validates and a fresh stack reaches readiness.
- Frontend and backend changes are reflected through the container development workflow.
- Migrations run safely on first startup and after restart.
- Data survives shutdown, rebuild, and restart without volume deletion.
- Backend tests, frontend checks, and a browser smoke test run from containers locally and in GitHub Actions.
- CI enforces at least 90% line and branch coverage independently for backend and frontend; missing reports and below-threshold results fail. Implement the full gate in E01, not at deployment time.
- A production build serves static frontend assets with no Node application backend.
- Document actual commands and observed results after implementation; remove the specification-only warning only when justified.

## E01.1 executable check baseline (2026-09-06)

The app skeleton and isolated check images now exist. The service stack, gateway,
source reload, persistent dependencies, migrations, and browser checks above remain
E01.2–E01.6 work. Do not use the planned startup command until those tasks land.

Run the current checks with Git and Docker only:

```sh
docker compose -p fillable-checks -f compose.test.yaml build
docker compose -p fillable-checks -f compose.test.yaml run --rm backend-test
docker compose -p fillable-checks -f compose.test.yaml run --name fillable-frontend-report frontend-test
mkdir -p frontend/coverage
docker cp fillable-frontend-report:/app/coverage/. frontend/coverage/
docker compose -p fillable-checks -f compose.test.yaml run --rm -v "$PWD/frontend:/source:ro" backend-test python /checks/check_coverage.py frontend /source
docker rm fillable-frontend-report
```

The named report container is disposable test output; removing it does not touch
application volumes. Tests erase old coverage before running. Dependency updates
use the pinned Node/Python images in `infra/`, `npm install --save-exact`, and
`pip-tools==7.5.3` with `pip-compile --generate-hashes`; rebuild after changing locks.
Runtime images are pinned by multi-platform digest. Application processes run as
non-root. E01.2 supplies separate production build targets.

Frontend uses React 19.2.8, Vite 8.2.2, Vitest 5.0.0, TypeScript 5.9.3 (compiler API
used by catalog checks), i18next 26.4.2 and react-i18next 17.0.13. The complete exact
versions/integrity hashes are in the npm lockfile. Backend direct versions are in
`backend/requirements.in`; every transitive dependency/hash is locked in
`backend/requirements.lock` for Python 3.13.12. Node is 24.14.0.

Official foundation references: [Vite runtime requirements](https://vite.dev/guide/),
[Vitest source inclusion](https://vitest.dev/config/coverage.html), and
[FastAPI container construction](https://fastapi.tiangolo.com/deployment/docker/).

## E01.2 runtime baseline

Base/development/production Compose definitions now exist. The initial runtime has
API, Vite (development only), and a non-root nginx gateway. Database/Redis/worker
and migration services arrive in E01.3. No application document writes exist yet.

```sh
cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build --wait
# Open http://localhost:8180; API health is /api/health.
docker compose -f compose.yaml -f compose.dev.yaml down
```

The frontend source/index and backend application source mount read-only; Vite and
Uvicorn reload them. Dependency/config changes require rebuilding. The gateway
forwards Vite WebSockets. API health currently proves process responsiveness only.

Local production-image verification (not deployment):

```sh
docker compose -p fillable-production-check -f compose.yaml -f compose.prod.yaml up --build --wait
# Open http://localhost:8181; this serves built assets without a Node runtime.
docker compose -p fillable-production-check -f compose.yaml -f compose.prod.yaml down
```

Use separate `DOCUMENTS_HOST_PATH` values when testing with retained application
data. Ordinary `down` preserves bind-mounted data and future named database/Redis
volumes; never add `-v` as a troubleshooting shortcut. The storage service and host
mount ownership setup arrive before document writes in E02. The current app never
writes retained files. Both published defaults bind 127.0.0.1; E08 will inspect the
actual shared ingress before choosing production ports/networking. No host ports
80/443 are claimed, and shared nginx is outside these Compose projects.

## E01.3 persistent services and migrations

The runtime now includes PostgreSQL 18.3, Redis 8.6.1 and RQ 2.7.0. PostgreSQL uses
its version-18 volume layout (`/var/lib/postgresql`); Redis enables append-only
persistence. Neither service publishes a host port. Ordinary shutdown preserves
both named volumes. The local example password is only for isolated development;
production requires a distinct privately configured password. The Compose value
must be URL-safe for the generated database URL.

Alembic runs `upgrade head` after PostgreSQL health and must finish successfully
before API/worker startup. The initial baseline creates only the migration version
record. Later schema changes are reviewed task migrations. API `/api/ready`
checks the database migration heads and Redis connectivity; `/api/health` remains
process-only. RQ starts with `app.worker_config`, the explicit
`rq.serializers.JSONSerializer`, and disabled job-description logging.

```sh
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml logs --tail 30 worker
docker compose -p fillable-checks -f compose.test.yaml run --rm backend-test
```

The test stack uses its own PostgreSQL tmpfs and Redis service. Migration tests
exercise repeat upgrades and preserve a synthetic marker; worker tests execute a
JSON queue round trip against real Redis. There are no retained document jobs
or quota bypasses. Worker source changes currently require a scoped restart/rebuild.

## E01.4 contract generation

After API changes, regenerate and commit both artifacts through Docker:

```sh
docker compose -p fillable-checks -f compose.test.yaml build
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/generated:/output" backend-test python /checks/export_openapi.py /output/openapi.json
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/generated:/app/generated" frontend-test npm run generate:api
```

No database or running API is required for generation. Rebuild afterward so tests
and production assets include the new generated types. CI runs these commands and
fails on a generated diff. The only generated paths are
`frontend/generated/openapi.json` and `frontend/generated/api.d.ts`; all authored
client logic stays under `frontend/src` and participates in coverage.
