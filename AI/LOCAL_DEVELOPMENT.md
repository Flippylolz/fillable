# Docker development and verification

E01.1–E01.5 provide the executable foundation. E01.6 verifies the clean-checkout
workflow below. Product accounts, document storage/quota services and the editor
remain later roadmap work. Live deployment is exclusively E08; these commands act
on isolated local Docker projects and do not contact the supplied server.

## Requirements and startup

Install Git and Docker with Compose. Use a POSIX shell (macOS/Linux or a suitable
Docker-integrated shell). No host Node, Python, PostgreSQL, Redis or browser
installation is required. From the repository root:

```sh
cp .env.example .env
docker compose -f compose.yaml -f compose.dev.yaml up --build --wait --wait-timeout 120
```

Open `http://localhost:8180`. The gateway routes frontend and API through one origin.
Ukrainian is the unconfigured UI default. The shell reports its API connection;
product login/library/profile/workspace pages are not yet implemented.

```sh
docker compose -f compose.yaml -f compose.dev.yaml down
```

Ordinary shutdown preserves PostgreSQL/Redis volumes and the document bind mount.
Never add `-v`, delete volumes, or prune the host to troubleshoot a failed startup.
Inspect only this project's logs and fix the failing dependency/configuration.

## Services and isolation

| Service | Behavior |
| --- | --- |
| `gateway` | Non-root nginx; development proxy with Vite WebSockets; production static assets and API proxy |
| `web` | Node/Vite, development only; source and index mounts reflect edits |
| `api` | Non-root FastAPI/Uvicorn; application source reloads in development |
| `db` | Private PostgreSQL 18.3, persistent volume at its version-18 `/var/lib/postgresql` layout |
| `redis` | Private Redis 8.6.1 with append-only persistence |
| `migrate` | One-shot `alembic upgrade head` after PostgreSQL health |
| `storage-init` | One-shot scoped storage directory ownership for API/worker UID 10001 |
| `worker` | Python RQ 2.7.0; starts after migrations and Redis health |
| `browser` profile | Non-root Playwright test image; never a production service |

API/worker startup waits for successful migrations. `/api/ready` checks the exact
migration heads and Redis; `/api/health` proves only process responsiveness. The
baseline migration creates Alembic's version record; domain schemas begin in E02.
Worker jobs use `rq.serializers.JSONSerializer` and disable job-description logging.

Only the gateway publishes a port, bound to `127.0.0.1`. Database/Redis are not
host-published. Compose explicitly owns only its namespaced containers, networks
and volumes. The existing production shared nginx is outside this lifecycle.

## Configuration

`.env.example` contains local-only defaults; copy it only if no local `.env` exists.
Never commit runtime secrets. Set a distinct private database password for
production. The current password must be URL-safe because Compose constructs the
SQLAlchemy URL; E08 must validate the final private runtime configuration.

| Setting | Current use |
| --- | --- |
| `COMPOSE_PROJECT_NAME` | Local runtime namespace; explicit `-p` takes precedence |
| `FILLABLE_DEV_PORT` | Loopback development gateway; default 8180; 0 requests an ephemeral port |
| `FILLABLE_UPSTREAM_PORT` | Loopback local production check; default 8181; real server allocation belongs to E08 |
| `DOCUMENTS_HOST_PATH` | Retained host path, default `./var/storage`, shared by API/worker |
| `POSTGRES_PASSWORD` | Required private-service database credential; example is development only |
| `DATABASE_URL`, `REDIS_URL` | Injected internal service connections |
| `STORAGE_ROOT` | Container document mount at `/data/documents` |

E02.3 implements shared retained writes, quota reservations, bounded staging,
disk headroom and crash cleanup. `storage-init` owns only the configured Fillable
root and its three immediate managed directories; use a dedicated path, never a
shared directory containing other services' data. It does not recursively chown
files. Both API and worker wait for it and run as UID 10001. Operator quota/capacity
configuration and batch reconciliation follow in E02.4/E02.5, before uploads.
Read [Storage quotas](STORAGE_QUOTAS.md) for the protocol. Local
production and development data paths/namespaces must be distinct when using real
data. Persistent staging and backups are outside MVP; retained versions remain required.

## Source edits, migrations and dependencies

Backend `app/` and frontend `src/`/index mount read-only into development services;
edit them in the checkout. Uvicorn reloads Python and Vite updates the open browser.
Vite permits the internal `gateway` hostname for container browser checks, without
allowing arbitrary hosts. Worker code changes require a scoped restart/rebuild.
Dependency, generated-client, and configuration changes require rebuilding images.

```sh
docker compose -f compose.yaml -f compose.dev.yaml run --rm migrate
docker compose -f compose.yaml -f compose.dev.yaml logs --tail 30 api worker
```

Runtime/tool images are pinned by version and multi-platform digest in `infra/`
and Compose. Exact frontend dependency versions/integrity are in `package-lock.json`;
backend direct requirements and transitive hashes are in `requirements.in` and
`requirements.lock`. Update with the pinned Node/Python Docker images,
`npm install --save-exact`, and `pip-tools==7.5.3`/`pip-compile --generate-hashes`.
Commit locks and rebuild. Node is frontend/build/browser tooling only.

## Required checks

Always give tests an explicit namespace independent of the runtime environment file:

```sh
docker compose -p fillable-checks -f compose.test.yaml build
docker compose -p fillable-checks -f compose.test.yaml run --rm backend-test
docker compose -p fillable-checks -f compose.test.yaml run --name fillable-frontend-report frontend-test
mkdir -p frontend/coverage
docker cp fillable-frontend-report:/app/coverage/. frontend/coverage/
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps -v "$PWD/frontend:/source:ro" backend-test python /checks/check_coverage.py frontend /source
docker rm fillable-frontend-report
```

Tests erase old reports. Backend runs Ruff, mypy, real PostgreSQL/Redis integration
and raw coverage gates. Frontend runs ESLint, catalog/copy negative tests, TypeScript,
build and Vitest coverage. Independently require at least 90% lines and branches,
including unimported application files and authored migrations. The named frontend
container retains disposable reports until copied; removing it does not affect data.

## Contract generation

After changing API schemas, generate and commit both artifacts through Docker:

```sh
docker compose -p fillable-checks -f compose.test.yaml build
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/generated:/output" backend-test python /checks/export_openapi.py /output/openapi.json
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/generated:/app/generated" frontend-test npm run generate:api
```

No live API/database is needed. Rebuild after generation. Required CI rejects drift
in `frontend/generated/openapi.json` and `frontend/generated/api.d.ts`; all authored
client behavior remains in covered `frontend/src`.

## Local production and browser checks

These verify images locally and do not deploy to the shared server:

```sh
docker compose -p fillable-browser-check -f compose.yaml -f compose.prod.yaml up --build --wait --wait-timeout 120
docker compose -p fillable-browser-check -f compose.yaml -f compose.prod.yaml -f compose.browser.yaml build browser
docker compose -p fillable-browser-check -f compose.yaml -f compose.prod.yaml -f compose.browser.yaml run --rm browser
docker compose -p fillable-browser-check -f compose.yaml -f compose.prod.yaml down
```

Use a free upstream port if 8181 is occupied. The production gateway contains built
static assets and no Node runtime. Playwright checks desktop/mobile real API flows
and retry; package/image versions match and use private shared memory rather than
host IPC. Full product/history/editor flows are added with those features.

## Repeatable fresh-checkout and reload verification

```sh
scripts/verify-development.sh
```

This exports the **Git index** to a fresh temporary directory. Stage intended
changes first; unstaged edits and ignored local secrets/dependencies are not copied.
It uses a unique Compose project and ephemeral loopback ports, starts development,
observes frontend HMR and backend reload in a real browser, restores the temporary
source edits, writes synthetic PostgreSQL/Redis markers, recreates the services in
production mode, verifies markers and removes only those markers, then runs the
production browser suite and verifies non-root/no-Node static serving.

The checkout is never mutated. The script stops its containers on exit and prints
the retained temporary path/project for diagnosis; it preserves volumes. This is
synthetic infrastructure evidence, not document quota/version-history acceptance.

References: [Compose readiness](https://docs.docker.com/compose/how-tos/startup-order/),
[Compose overrides](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/),
[Playwright Docker](https://playwright.dev/docs/docker), [Vite](https://vite.dev/guide/),
[Vitest coverage](https://vitest.dev/config/coverage.html), and
[FastAPI containers](https://fastapi.tiangolo.com/deployment/docker/).

## Static build version

Unconfigured builds show `version: development`. Supply public source metadata
when building the production gateway; changing the argument recompiles its assets:

```sh
VITE_APP_COMMIT_SHA=$(git rev-parse HEAD) docker compose -f compose.yaml -f compose.prod.yaml up --build --wait
# Match browser verification to the metadata supplied to that build:
docker compose -f compose.yaml -f compose.prod.yaml -f compose.browser.yaml run --rm -e EXPECTED_APP_VERSION=$(git rev-parse --short=7 HEAD) browser
```

A variable set only on the running nginx container cannot change compiled assets.
The ordinary fresh-development verifier builds without metadata and checks the
fallback. Required CI also builds with its checked-out source commit and checks
that value. E08 will supply the selected release revision and verify live delivery.

## Editor corpus prototype

Start the explicit synthetic proof override, then open `/prototype.html`:

```sh
docker compose -f compose.yaml -f compose.dev.yaml -f compose.editor-proof.yaml up --build --wait
```

The page is a test harness
for the source-derived Ukrainian corpus. It is excluded from the production entry
and makes no retained document writes. Source code remains in the reusable application
editor modules; the synthetic JSON and harness live under `frontend/prototype`.

Regenerate after mapper changes (the test Compose mount supplies `/fixtures`):

```sh
docker compose -p fillable-checks -f compose.test.yaml run --rm --no-deps --user "$(id -u):$(id -g)" -v "$PWD/frontend/prototype:/output" backend-test python /checks/export_editor_fixture.py /output/document.json
```

The fresh-checkout verifier now runs both reload and corpus-editor browser checks.
It retains browser screenshots/traces in its printed temporary directory's
`browser-results/`; CI supplies an absolute `FILLABLE_BROWSER_REPORTS` directory
inside its uploaded reports. E00.4 adds memory-only synthetic export/reopen routes,
which are absent from normal development and production. It adds no account or
retained-file API. Independently render its downloaded DOCX files with:

```sh
scripts/verify-docx-render.sh /absolute/path/to/browser-results
```

This builds a separate pinned LibreOffice/Poppler QA image and checks original
identity, three-page rendering, unchanged-page pixels and Ukrainian text. Inspect
the generated original/edited PNGs when changing transformations. E05.3 adds the
five-page `multiline.docx` browser export, repeated Ukrainian/astral text counts and
non-overlapping multiline control checks. The pinned QA image uses LibreOffice 25.2
and Noto Color Emoji; older 7.4 rendering did not handle multiline controls correctly.
Reports contain
only synthetic fixture data; no application storage paths or user uploads are used.

## Local accounts and sessions (E02.1)

Normal migrations/startup create no user or default password. Provision a local
account through the running API container with a private interactive password:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec api python -m app.accounts.cli provision --email you@example.test --display-name "Your name" --role admin
```

Use `--language en` to provision English; Ukrainian is the default. Reset a
credential with the `reset-password --email you@example.test` action; reset revokes
all existing authenticated sessions. For noninteractive operation, use
`--password-stdin` with input from a private source. Never put passwords in command
arguments, tracked configuration or logs. The operator commands reuse account
validation and hashing, with no public signup or administrator screen.

Set `FILLABLE_PUBLIC_ORIGIN` to the exact browser origin. The local development
example is `http://127.0.0.1:8180`; alternate hostnames/ports are deliberately distinct.
For the local production smoke port, start with
`FILLABLE_PUBLIC_ORIGIN=http://127.0.0.1:8181` in the Compose environment. The browser
verifier instead uses its private `http://gateway:8080` origin. HTTP sessions use
HttpOnly/SameSite=Strict, host-only `fillable_session_v1`, Secure=false, CSRF tokens
and exact-origin validation including port; HTTPS configuration sets Secure=true.
The deployment HTTP choice and port-sharing limitation remain D019.

The fresh-checkout and CI browser harnesses explicitly provision the synthetic
`browser@example.test` fixture using `fixtures/auth/browser-password.txt`, only in
their isolated project databases. This fixture is never created by normal startup
or deployment. The normal operator path has no fallback/default credentials.

## Storage maintenance and capacity

E02.4 adds one-shot `python -m app.storage.maintenance` commands inside API/worker
containers: `capacity`, `reconcile`, `accounts`, and `inventory`. See
[Storage quotas](STORAGE_QUOTAS.md#e024-deletion-and-maintenance) for exact commands,
cursor handling, conservative counter repair and failure semantics. These commands
are not scheduled yet; periodic execution is E07.3. They do not prune version history.

The environment example now exposes the shared exact-byte file/staging/headroom
limits and lease duration. `configuration.configured()` validates them when building
the service; API/worker use identical Compose settings. Changing configuration
requires recreating the affected containers. Keep per-user quota allocation changes
separate from operating capacity; E02.5 supplies the quota commands.

The fresh-index verifier now creates retained synthetic data through the shared
service, deletes an independent copy without changing the original, and verifies
bytes/accounting from both API and worker after development-to-production recreation.
It then runs storage reconciliation, inventory and capacity commands. It preserves
its isolated synthetic data/volumes and does not contact the deployment target.

E02.5 supplies `python -m app.storage.quota_cli default|override|inherit|show` for
trusted operators, with exact-byte arguments and audited changes. Use the examples
in [Storage quotas](STORAGE_QUOTAS.md#e025-usage-and-operator-allocation-commands).
These commands share database locks with retained allocations; lowering a limit
preserves existing bytes. Ordinary web users receive only their authenticated
`GET /api/storage/usage` response. No quota administration HTTP route is exposed.

E02.6 adds a separate synthetic `profile@example.test` account to the explicit CI
and fresh-index browser setup. Desktop/mobile checks persist a Unicode display name,
reject an incorrect current password, rotate credentials, revoke a second browser
session, and restore the fixture through the UI. Normal startup provisions neither
browser fixture. Profile screenshots are retained under the verifier's printed
`browser-results/production/run` directory.

E03.3 extends the fresh-index proof with an API upload and committed retry using
the synthetic profile account. After recreation, API and worker verify the owned
initial revision and immutable original. The worker receives the QA origin explicitly
for this check; normal worker configuration has no browser-origin dependency.
See [Document persistence](DOCUMENT_PERSISTENCE.md) for the upload header/body
contract, admission bounds and the gateway's streaming configuration.

## Processing dispatcher

E03.5a adds the private Python `dispatcher` service beside the RQ worker. Both use the
same pinned backend image; only the worker mounts document storage. The dispatcher
recovers PostgreSQL processing intent into the JSON-only `fillable` queue in bounded
batches. No host cron or public port is added. Backend job/dispatcher code changes
require rebuilding/recreating those services; only the API has the existing development
reload watcher. `scripts/verify-development.sh` explicitly verifies actual job completion
and preserved saved bytes/quota through the isolated dispatcher/worker stack. See
[Processing](PROCESSING.md) for retry and source-revision guarantees.
