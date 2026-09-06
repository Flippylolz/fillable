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
