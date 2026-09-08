# Deployment target and shared-service constraints

Status: the user and shared nginx configuration task confirmed D024: the existing
shared owner has deployed internal HTTPS 3200. Fillable's app and TCP relay are now
deployed and verified through Actions. [Deployed acceptance](DEPLOYED_ACCEPTANCE.md)
records public readiness, authenticated flows, persistence and existing-service checks.

Public documentation uses `<DEPLOY_HOST>` and `<DEPLOY_USER>` placeholders. Read the
ignored local deployment configuration for actual identity; never publish credentials,
private paths or keys. Deployment remains last through verified GitHub Actions artifacts.

## Current routing contract

```text
https://<DEPLOY_HOST>:3200 → Fillable TCP relay (owns host 3200)
                          → shared nginx TLS 3200 on wef-edge
                          → http://fillable-gateway:8080 → private API
```

Set `FILLABLE_PUBLIC_ORIGIN=https://<DEPLOY_HOST>:3200`. The relay passes encrypted
bytes unchanged; the existing hostname certificate is owned by shared nginx. Preserve
HSTS, Forecast HTTP 3000, WEF HTTP 3100/HTTPS 443 and every unrelated service/route.
Do not publish host 3200 from shared nginx Compose: its existing 80/443 mappings stay
unchanged. Only Fillable's gateway and relay join `wef-edge`; databases stay private.

Contact the existing shared nginx configuration task before ingress changes. Its
owner has confirmed no changes or reload are needed when the gateway appears via
Docker DNS. Do not activate the legacy HTTP include, edit templates/manager/current
release/state/certificates, or recreate shared nginx. See [Server runtime](SERVER_RUNTIME.md).

## Preflight and acceptance

Use strict SSH host-key checking and the existing authorized identity. Inspect
occupied/reserved ports, capacity and unrelated container/route baselines read-only.
Recheck that host 3200 is free before first relay publication and the shared container
has no binding for it. Use its actual serving configuration for `nginx -t`.

Discover the shared container's current `wef-edge` IP; verify TLS with the real hostname
and normal CA trust. Do not pin its dynamic IP or disable verification. Internal
readiness may return 502 before application startup; after startup require 200 through
the relay and exact public HTTPS origin. Check Secure/HttpOnly/SameSite cookies,
CSRF, exact origin including port, public assets, authenticated DOCX flows and persistence.
Cookies are not isolated by port; retain Fillable's distinct cookie name.

Upgrade only the idle Fillable bootstrap using the reviewed guarded installer before
applying the HTTPS release. Preserve generated database credentials, SSH keys and data.
Deploy immutable passing artifacts into `fillable-production` with bounded resources,
namespaced volumes and a dedicated document root. Enforce independent raw 90% line
and branch gates for both application components and verified required CI before rollout.

Compare unrelated identities, start times, restarts, health and route/HSTS observations
before/after. Failure stops only Fillable's relay, preserving the owner-managed TLS
listener and application data for forward repair. No host-wide pruning, daemon restart,
unrelated upgrades, firewall edits, volume deletion, backups or blanket rollback.

The historical observations below document the earlier HTTP discovery; D024 and the
current owner handoff above govern deployment now.

## Historical E08.1 observations — HTTP scope superseded by D024

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
