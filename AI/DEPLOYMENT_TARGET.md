# Deployment target and shared-service constraints

Status: E08.1 verified SSH access, capacity, existing services and WEF shared-nginx ownership. Public HTTP port 3200 is selected; external reachability passed after the user opened/forwarded the port. No application deployment has occurred.

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
| Public nginx port | 3200, selected and checked unused during E08.1; recheck before binding |
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
- HTTP does not encrypt credentials, cookies, or documents. Set `FILLABLE_PUBLIC_ORIGIN` explicitly and use the HTTP cookie configuration in D019: distinct cookie name, HttpOnly, SameSite, Secure=false, CSRF, and exact-origin validation including the port. Cookies are not isolated by port; changing the listener does not isolate sessions from other services on the hostname.

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


## E08.1 observed baseline and scoped topology

Preflight followed E07's verified merge. SSH succeeded using existing authentication
and strict host-key checking. The host is Linux amd64 with eight CPUs, approximately
7.3 GiB RAM (5.4 GiB available at the sample) and 807 GiB free on the root filesystem.
Docker 29.5.1 and Compose 5.1.3 are available. Noninteractive sudo is unavailable;
Docker access is already authorized. These are observations, not peak-load promises.

Fifteen existing containers belong to WEF production/candidate/shared-edge, Forecast,
DDNS and VPN projects. All existing container identities/states were preserved during
preflight. The WEF candidate edge was already unhealthy while its HTTP root answered
200; this is baseline, not a Fillable regression or an authorization to repair it.
Other sampled roots: shared HTTP 404, WEF production 200, Forecast web 200, Forecast
API root 404. Existing public HTTPS answered 200 with its unchanged HSTS header.
The shared nginx container's restart count is zero; its identity/start time remained
unchanged. No application configuration, volume or existing route was modified.

WEF owns the containerized shared edge. The authoritative installed manager is an
operator-owned snapshot, not a Git checkout: `ops/scripts/deploy/shared_edge_release.py`
and its `ops/infra/nginx` templates. Its managed root has versioned releases and
atomic current/previous pointers. Activation validates a complete candidate as the
serving UID, verifies upstreams, switches the pointer and can gracefully reload.
Renewal separately validates the actual current config before signaling HUP. Actual
private roots and connection identity remain in ignored deployment configuration.
The serving command uses `/etc/nginx-edge/current/active.conf`; testing only nginx's
image-default config is insufficient. The actual serving configuration passed nginx -t.

Shared nginx currently publishes only host 80/443 on the existing private `wef-edge`
network. Adding a Docker port binding would recreate that shared container. Instead,
E08.3 will verify a Fillable-owned TCP relay: host 3200 → shared nginx's new internal
HTTP listener → Fillable's private gateway. The relay transports bytes only; shared
nginx continues to own HTTP routing. The existing pinned nginx supports its stream
module, so this needs no competing TLS manager or shared-container recreation. Only
the relay and gateway join the existing ingress network; database/Redis remain private.
The existing manager must own the additive route and its regeneration path, validate
all effective configuration, preserve concurrent unrelated edits and gracefully reload.

Choose the unused Compose namespace `fillable-production` and a dedicated operator
home subtree, with document/database/Redis persistence scoped to that namespace.
No such project or directory existed during discovery. Keep actual private paths in
runtime configuration. Port 3200 was absent from running listeners and checked
managed Compose files, then successfully bound by a temporary isolated HTTP probe.
The probe used a cached pinned image, read-only root, nonroot UID, 64 MiB/0.25 CPU,
no persistent mount and automatic removal. Initial public reachability failed; the
user reported opening/forwarding TCP 3200, and the retry reached the expected fixed HTTP probe response publicly. The probe
was stopped and automatically removed after both attempts.
Recheck allocations and existing-service baselines immediately before rollout.

D019 was explicitly reaffirmed after discovering hostname-wide HSTS: HTTP on the new
port, no Fillable TLS/HTTPS work. Browsers with learned HSTS may upgrade this URL and
fail. Preserve existing TLS/HSTS routes and state; record this compatibility limit
rather than silently changing the scheme. Port forwarding, immutable artifact/CI
wiring, managed ingress activation and full deployed MVP verification remain separate
E08 tasks. These preflight observations do not claim the application is deployed.
