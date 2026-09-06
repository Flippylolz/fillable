# Deployment target and shared-service constraints

Status: user-provided target recorded; server access, running services, ports, and nginx ownership have not been inspected. Deployment remains final epic E08 through GitHub Actions.

This public document uses `<DEPLOY_HOST>` and `<DEPLOY_USER>` placeholders. The supplied values are retained in the ignored local `AI/DEPLOYMENT.local.md`; use deployment environment configuration during E08. Do not commit endpoint/account values, credentials, or private keys. Missing local configuration on another checkout is an environment handoff need, not a reason to publish it here.

## Known inputs

| Item | Recorded value |
| --- | --- |
| SSH host | `<DEPLOY_HOST>` |
| SSH user | `<DEPLOY_USER>` |
| User-supplied connection command | `ssh <DEPLOY_USER>@<DEPLOY_HOST>` |
| Existing workloads | Other services run on this server and must be preserved |
| Public ingress | Use the existing shared nginx |
| Possible nginx source repository | `WEF` — user-suggested location, not verified |
| Public nginx port | Unassigned numeric value; select a new unused HTTP listener as `FILLABLE_PUBLIC_PORT` |
| Private gateway port/network | Separate upstream, discovered for the actual host/container nginx topology |
| Public application URL | `http://<DEPLOY_HOST>:<PORT>`; `<PORT>` is the new public nginx listener |
| Environments | Local development and production; disposable CI test stacks only |
| Backups | Outside MVP by user decision; no backup destination or pre-deployment backup requirement |

Record sanitized deployment evidence here during E08; keep concrete connection values, private paths, credentials, and keys in local/deployment environment configuration. Public evidence can identify the release commit and verification results without exposing connection details.

## Preflight in E08

1. Connect using the supplied identity and existing authentication. Verify the SSH host identity through the available trusted setup; do not disable host-key checks to make deployment work.
2. Read relevant server/repository instructions. Inspect existing service/container names, Compose projects, listening sockets, published ports, resource use, and storage paths using read-only checks.
3. Identify the active nginx instance: host service or container, actual config/include paths, TLS management, upstream networking, and its established validation/reload process.
4. Look for a repository named WEF in the relevant deployment directories or configured projects. If it manages nginx, read its instructions and inspect its working state and deployment workflow. Do not assume WEF exists or overwrite local changes.
5. Identify the authoritative nginx configuration. If repository-managed, prepare the focused change there and use its established apply process; do not edit generated/live files in a way the manager will overwrite later.
6. Record baseline service states and lightweight checks for existing routes affected by the shared proxy. Do not inspect or log unrelated application secrets or private content.
7. Choose an unoccupied high public HTTP port, check running and configured/reserved allocations, and recheck immediately before binding it. Record it as `FILLABLE_PUBLIC_PORT`. Select a distinct private `FILLABLE_UPSTREAM_PORT` only if the gateway requires host publication. Never evict an existing listener or reuse another service's reserved port. Verify outside reachability through the existing network/firewall setup; any new rule must be limited to Fillable's selected public port and use the established owner process.
8. Choose an unused Compose project namespace and dedicated directories/volumes. Set CPU, memory, worker-concurrency, and disk limits compatible with the host's remaining capacity.

## Routing design

```text
Browser → http://<DEPLOY_HOST>:<PUBLIC_PORT>
        → existing shared nginx → private Fillable gateway
                                   ├─ static React application
                                   └─ /api → private FastAPI service
```

- Use a small nginx gateway inside the Fillable Compose project for static assets and application routing. Existing shared nginx owns the new public HTTP listener. Existing TLS services remain unchanged; no certificate or HTTPS redirect is required for Fillable's accepted origin.
- With host-native shared nginx, prefer publishing the gateway only on loopback at the selected port. Verify effective reachability and Docker behavior on the actual host.
- If shared nginx is containerized, its loopback is not the host's loopback. Follow the existing private upstream-networking pattern, attaching only the gateway as necessary. Do not expose PostgreSQL/Redis or broaden the bind to all interfaces merely to make an upstream reachable.
- Do not bind Fillable to the host's public ports 80/443, take over the default virtual host, or start a competing TLS/certificate manager.
- Add a narrowly scoped server include for `<DEPLOY_HOST>` listening on `FILLABLE_PUBLIC_PORT`, serving the application at `/`. If shared nginx is containerized, its new port publication must be managed by the existing owner; do not recreate or reconfigure that service independently. Preserve existing upstreams, certificates, and unrelated settings.
- Match upload-size limits, forwarded headers, and editor connection requirements at the app route without changing global defaults for other services. Verify static assets, APIs, cookies, downloads, and editor connections at the exact public origin including its port.
- HTTP does not encrypt credentials, cookies, or documents. Set `APP_PUBLIC_URL` explicitly and use the HTTP cookie configuration in D019: distinct cookie name, HttpOnly, SameSite, Secure=false, CSRF, and exact-origin validation including the port. Cookies are not isolated by port; changing the listener does not isolate sessions from other services on the hostname.

This supersedes the earlier Caddy proposal. Local development uses a project-owned nginx gateway to provide the same application routing without requiring the production server.

## Applying and verifying changes

- Build/test in GitHub Actions and deploy only passing artifacts, including the mandatory 90% coverage gates.
- Start Fillable in its isolated namespace and check its selected upstream port before connecting the public route.
- Preserve a scoped diff/recovery copy of the nginx change. Coordinate shared-config writes with the existing manager so another deployment cannot be overwritten by stale state.
- Validate the complete effective nginx configuration using `nginx -t` in the actual host/container/config context. If existing configuration is already invalid, do not reload it or repair unrelated services as part of this rollout.
- Apply through the established nginx manager and use a graceful reload after successful validation. Do not restart shared nginx, Docker, or unrelated services as a routine deployment step.
- Verify Fillable through shared nginx and repeat the recorded checks for existing routes/services. Compare with the preflight baseline and record results.
- If the new route or application causes regression, stop rollout and revert only Fillable's change through the same configuration owner, validate, and gracefully reload. Do not restore a whole shared config tree over concurrent changes.
- Keep application/data recovery separate from the proxy change. Follow the schema-aware recovery plan in [CI and deployment](CI_CD.md).
- D018 excludes backups and backup/restore drills. Verify persistent storage and non-destructive migration behavior; do not require a snapshot or backup before rollout. Previous images can recover application code only when schema-compatible. No plan can recover lost database/files from a backup that does not exist; local version history does not provide disaster recovery.

References: [nginx configuration reload behavior](https://nginx.org/en/docs/control.html), [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/).

## Commands must remain scoped

Every Compose operation must identify Fillable's verified project name and configuration files. Preserve other projects' containers, volumes, networks, ports, routes, and persistent data. Do not use host-wide pruning, blanket container stop/remove commands, Docker daemon restart, broad firewall changes, or whole-server upgrades to complete this deployment.

If an unavoidable conflict requires changing an unrelated service, first finish the safe independent work, then describe the concrete conflict and obtain the user's direction for that additional scope.
