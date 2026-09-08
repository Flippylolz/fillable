# Isolated server runtime — E08.3

Fillable installs a private receiver and fixed runtime under the supplied account's
dedicated `fillable` directory. E08.3 prepares this boundary; E08.4 performs the first
application rollout through Actions. D024 now requires HTTPS port 3200 through externally managed TLS.
No shared service is restarted or recreated, and no certificate or TLS policy changes.

## Deployment boundary

A newly generated dedicated SSH key is authorized with `restrict` and a forced Python
receiver command. Existing authorized keys are retained. The receiver accepts only
`check`, `receive <40-character commit> <SHA-256>` and `apply` with those same arguments. A source-bound `provision` command also accepts bounded private initial-account input after a successful release, and refuses to run when any users exist. It delegates to the existing account CLI with password stdin; there is no reset or deletion command.
It cannot select a shell, project, filesystem path, arbitrary Compose file or command.
A process lock serializes receiver operations. Installation preserves an existing
matching configuration on retry and refuses to overwrite another installation.

The installer copies a fixed allowlist of reviewed Compose/configuration/helper files.
Their fingerprints are verified at every preflight. Uploaded source is evidence and
is never executed or used as Compose input. The complete bounded archive is retained;
apply revalidates it and its image/config digests. Docker loads the delivered images,
then their platform and revision labels must match. E08.9 resolves only the checked
config or OCI manifest digest from the same archive, accounting for classic versus
containerd image stores. Runtime image selection and private release state use that
exact host ID with builds removed and application image pulls disabled. No mutable
tag or storage-driver change is permitted.

The database password is generated privately on the server and is never returned by
the installer. The exact HTTPS origin, dedicated document path and 2 GiB disk headroom
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
relay uses the already pinned nginx stream implementation; the shared nginx terminates TLS and forwards private HTTP. Local proof uses an isolated equivalent network and no public host publication.

All established runtime CPU/memory ceilings, private storage, read-only application
roots and bounded logs remain. Preflight requires the observed Linux amd64 Docker
platform, an unambiguous shared-nginx owner, valid effective nginx configuration,
available memory and disk headroom. Port 3200 is checked before first publication;
configured port reservations must also be rechecked before the first E08.4 rollout.

## Shared nginx integration

The shared nginx configuration task owns the existing TLS listener and certificate.
The user and owner confirmed its interface: internal TLS 3200 on `wef-edge`, variable
Docker-DNS upstream `http://fillable-gateway:8080`, preserved Host including port,
forwarded HTTPS scheme/3200 and 12 MiB body limit. Shared Compose publishes only 80/443.
No activation, template/manager patch, config replacement or nginx reload is required.
Contact that task before ingress changes. Legacy edge helpers remain in the fixed
receiver file allowlist for installation compatibility; the runtime never calls them.

Preflight requires `ingress_mode=external_tls`, an exact HTTPS origin, no shared host
3200 binding and a verified certificate/hostname connection to the dynamically
inspected edge IP. A 502 is allowed only before the app starts. After starting the
relay, an end-to-end TLS request through loopback 3200 must return readiness 200.

For the existing idle bootstrap, run the reviewed installer's `upgrade-https` mode
with merged source and its full commit. It holds the Fillable release lock, refuses
any existing app containers or release state, verifies every old installed fingerprint,
and replaces only fixed receiver files, their fingerprints, installation revision and
public origin. Database credentials, SSH authorization, documents and shared nginx
remain untouched. Concurrent changes fail; partial writes are rolled back only when
they still contain this upgrade's bytes. Never execute the old HTTP receiver apply.

## Schema-aware failure handling

The installed policy accepts only the reviewed `0013_maintenance_state` image schema.
A new empty database or that same existing schema may proceed. An older, unknown or
multiple database head, or an image requiring another schema, stops for a reviewed
forward plan before starting the application. Reviewed migrations remain startup
dependencies and readiness verifies the resulting schema. No downgrade, data drop,
volume deletion, host-wide shutdown/pruning or backup operation exists in this path.

On ingress/verification failure only the Fillable relay is stopped; the externally
owned TLS listener is never removed or changed. Private application/database data remains
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

E08.3 bootstrap is now verified from corrective PR #73's merged source. The dedicated
key passes receiver readiness and rejects arbitrary shell commands; every existing
container baseline matched before/after. The production environment permits only
main and holds the four dedicated transport secrets. Optional Docker health state is
read safely, including containers without healthchecks.

E08.7 follows the user's private account-creation choice. Actions holds only the four
transport secrets; it does not receive account credentials. After artifact application,
`check-public-release.sh` verifies public readiness, the login page, anonymous session
cookie policy, private-data denial and origin/CSRF rejection. Its public receipt
explicitly records `authenticated_acceptance: pending`; a green Actions rollout alone
is not completed MVP acceptance.

The authorized operator creates the initial user privately using the containerized
account CLI and password stdin. Do not reset an existing account automatically. Then
run `smoke-release.sh` privately with `FILLABLE_PUBLIC_ORIGIN`, `FILLABLE_INITIAL_LOGIN`
and `FILLABLE_INITIAL_PASSWORD`. It requires matching successful deployment evidence
and the manifest's exact immutable image/revision. No SSH key or provisioning command
is used by this smoke utility. Credentials must never be shell arguments, public logs,
GitHub secrets or committed files. The restricted receiver is updated through the guarded D024 predeployment upgrade.

The authenticated checker verifies HTTPS Secure cookie policy, exact-origin/CSRF rejection,
synthetic upload, worker completion, a saved revision, and byte-exact original/current/
history downloads. An unchanged idempotent write may retry a temporary file-reader
conflict. Failed checks remove stale evidence and fail. Content-free private acceptance
evidence contains only source, synthetic digests, version count and status. Synthetic
documents remain retained and quota-charged. Complete E08.5's real browser version
badge, broader MVP and restart/persistence acceptance before marking rollout done.

The Docker archive check covers both legacy and OCI metadata paths. An OCI index
must reference exactly the two expected image configurations with only their Fillable
source tags, verified manifest bytes and no nested indices. Legacy repository aliases
are likewise restricted. The real Docker-produced archive passed these checks;
controlled alternate-tag/config/index mutations are rejected before image loading.
