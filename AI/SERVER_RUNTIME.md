# Isolated server runtime — E08.3

Fillable installs a private receiver and fixed runtime under the supplied account's
dedicated `fillable` directory. E08.3 prepares this boundary; E08.4 performs the first
application rollout through Actions. HTTP port 3200 remains the accepted origin.
No shared service is restarted or recreated, and no certificate or TLS policy changes.

## Deployment boundary

A newly generated dedicated SSH key is authorized with `restrict` and a forced Python
receiver command. Existing authorized keys are retained. The receiver accepts only
`check`, `receive <40-character commit> <SHA-256>` and `apply` with those same arguments.
It cannot select a shell, project, filesystem path, arbitrary Compose file or command.
A process lock serializes receiver operations. Installation preserves an existing
matching configuration on retry and refuses to overwrite another installation.

The installer copies a fixed allowlist of reviewed Compose/configuration/helper files.
Their fingerprints are verified at every preflight. Uploaded source is evidence and
is never executed or used as Compose input. The complete bounded archive is retained;
apply revalidates it and its image/config digests. Docker loads the delivered images,
then their IDs, platform and revision labels must match. Runtime image selection uses
those IDs with builds removed and application image pulls disabled.

The database password is generated privately on the server and is never returned by
the installer. The exact HTTP origin, dedicated document path and 2 GiB disk headroom
are explicit private settings. Existing settings survive installation retries. GitHub
receives only the dedicated SSH identity and trusted host-key data through production
environment secrets; the production environment must restrict deployment to main.
No personal SSH private key or fixed public browser-fixture password is deployed.

## Services and persistence

`compose.server.yaml` overlays the tested base and production definitions. Its fixed
`fillable-production` namespace owns PostgreSQL/Redis volumes and a dedicated document
bind. API, worker and maintenance use the same quota-enforced document root. Retention
remains keep-all. The effective configuration rejects unexpected mounts, images, build
settings, privileges, host networking, missing bounds or additional published ports.

Only a 64 MiB / 0.25 CPU TCP relay publishes host port 3200. The route is:

```text
host :3200 → Fillable TCP relay → existing shared nginx :3200
                                    → private Fillable gateway :8080 → API
```

Gateway and relay join the existing `wef-edge` network with a distinct Fillable gateway
alias. The database, Redis and API have no host publication. Existing 80/443 listeners,
shared-container port mappings and other application services remain unchanged. The
relay uses the already pinned nginx stream implementation; the shared nginx handles
HTTP. Local proof uses an isolated equivalent network and no public host publication.

All established runtime CPU/memory ceilings, private storage, read-only application
roots and bounded logs remain. Preflight requires the observed Linux amd64 Docker
platform, an unambiguous shared-nginx owner, valid effective nginx configuration,
available memory and disk headroom. Port 3200 is checked before first publication;
configured port reservations must also be rechecked before the first E08.4 rollout.

## Shared nginx integration

The authoritative installed owner is the WEF shared-edge `ops` tree, not a Git checkout.
Its inspected source/template fingerprints are recorded privately. The installer does
not edit that manager. On first Actions apply, the adapter refuses an unexpected source,
adds a small reentrant process-lock helper to the existing activate/rollback entry
points, and uses the same lock while preparing and activating Fillable's extension.
This coordinates manager writers; it does not claim control over arbitrary manual
filesystem changes by noncooperating actors.

One marked include is added inside HTTP in the three authoritative templates and in
a new release derived from the current configuration bytes. This preserves later
regeneration and does not reconstruct unrelated routes from an older template. The
current hook/issuance files are retained; certificate/key trees are not copied or
changed. The owner validates the complete candidate with its pinned image and applies
through its existing atomic pointer and graceful reload process. Failed validation
cannot activate the candidate. Concurrent source/template changes abort activation.

The extension owns only internal HTTP 3200, the exact configured hostname and private
Fillable upstream. Its body/time limits and content-free logging are scoped to that
listener. Recovery creates a new release from the then-current configuration, removing
only Fillable's marked include while preserving intervening unrelated edits. It never
uses a blanket previous-shared-release rollback. The local real-manager proof verifies
activation, graceful reload, existing-route preservation and scoped removal after a
concurrent owner edit, with unchanged shared container ID/start time/restart count.

## Schema-aware failure handling

The installed policy accepts only the reviewed `0013_maintenance_state` image schema.
A new empty database or that same existing schema may proceed. An older, unknown or
multiple database head, or an image requiring another schema, stops for a reviewed
forward plan before starting the application. Reviewed migrations remain startup
dependencies and readiness verifies the resulting schema. No downgrade, data drop,
volume deletion, host-wide shutdown/pruning or backup operation exists in this path.

On ingress/verification failure the relay is stopped; a newly added Fillable include is
removed through the scoped manager process. Private application/database data remains
for diagnosis and forward repair. `attempt.json` records only source, phase and status;
failed attempts do not replace the last successful `state.json`. Release archives and
receipts remain available. First deployment has no earlier application to restore.

A later image recovery requires a previously verified artifact and an explicit review
of both schema and stored-document compatibility. Matching a schema name alone does
not establish semantic backward compatibility. Prefer a tested forward repair through
the current-main Actions gate. Do not rebuild arbitrary server source, assume switching
an image reverses a migration, or promise restoration of lost data. The current gate
intentionally does not deploy arbitrary older main revisions.

## Verification and remaining rollout

Docker contract tests exercise receiver input/archive replay, installation retry/key
preservation, failed-attempt records, scoped edits and competing processes. Required CI
also generates the actual server Compose configuration and proves unsafe changes fail.
The real installed-manager source was exercised locally with the actual private app
and relay: six desktop/mobile save/badge cases, full Fillable restart with identical
stored bytes/digests/quota counters, and scoped removal preserving an owner edit.
These are isolated synthetic checks, not a deployed MVP claim.

Application rollout remains E08.4 after this task's verified merge and private bootstrap.
It must verify the externally reachable exact origin with authenticated synthetic flows.
E08.5 verifies the broader deployed MVP and persistence. Existing-service container
identity/start/restart/health and existing route/HSTS results are compared before/after
apply; production reports expose only safe source/digest/status evidence.

The Docker archive check covers both legacy and OCI metadata paths. An OCI index
must reference exactly the two expected image configurations with only their Fillable
source tags, verified manifest bytes and no nested indices. Legacy repository aliases
are likewise restricted. The real Docker-produced archive passed these checks;
controlled alternate-tag/config/index mutations are rejected before image loading.
