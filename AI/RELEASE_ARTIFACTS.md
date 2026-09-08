# Verified release artifacts — E08.2

The manual `.github/workflows/deploy.yml` accepts the full current protected-main
commit. Its credential-free verification job requires the latest push CI run for
that exact revision, the expected active workflow identity, and successful `checks`,
`upgrade-checks` and `ci-required` jobs from the same completed run attempt. Missing,
failed, cancelled, skipped, stale or mismatched evidence fails closed. The gate
rechecks the latest run and main ref after retrieving jobs, and again after building.
It does not fall back to an older successful run. The existing CI owns the independent
raw 90% line and branch gates, source provenance and real negative coverage probes.

Deployments use one non-cancelling concurrency group and the `production` environment.
E08.3 must restrict that environment to main and install a dedicated restricted SSH
receiver before rollout. Repository protection remains a separately verified setting;
the evidence gate does not claim to configure or query administrator-only rules.

`scripts/build-release.sh` builds Linux amd64 backend/gateway images from a Git archive
of the exact clean committed revision. Ignored and untracked workspace files cannot
enter the Docker build context. Both images carry the full revision label and the
frontend receives that revision through `VITE_APP_COMMIT_SHA`. Docker image IDs,
platforms, revision, CI run ID and file digests are recorded in a versioned manifest.
The transferred tar contains only that manifest, compressed Docker images and the
same source archive. Its SHA-256 identifies the exact transferred bytes. The server
must load these images; rebuilding different source or resolving a mutable latest tag
is outside the release protocol.

The archive verifier checks outer and inner digests, bounded decompression, safe
nonduplicate file entries, Git archive commit identity, and the Docker config bytes
against their declared image IDs, platform, tags and revision labels. These digests
bind bytes produced by trusted CI; they are not an independent cryptographic signature.
The receiver must also inspect loaded image identities before applying them.

`scripts/ship-release.sh` uses a dedicated private key and pinned known-hosts data from
production environment secrets (`FILLABLE_DEPLOY_HOST`, `FILLABLE_DEPLOY_USER`,
`FILLABLE_DEPLOY_KEY`, `FILLABLE_KNOWN_HOSTS`). It requires protocol-1 readiness,
verified receipt of the exact source/digest, then a successful apply result for that
source. Missing receiver or incomplete validation fails the workflow. Connection
identity, raw receiver output, keys and runtime secrets are not published as artifacts.
Only source/digest/CI metadata and a reconstructed successful deployment result are
uploaded. Private runtime setup and the receiver implementation belong to E08.3;
actual Actions rollout and deployed application verification belong to E08.4–E08.5.

HTTP port 3200 and the existing shared-nginx owner remain the accepted target. No
application is deployed by introducing this workflow. Contract tests exercise rejected
CI states and races, archive tampering, unsafe/duplicate entries and image identity
mismatches; actual image archive and workflow evidence are recorded in the epic ledger.

E08.7 adds credential-free public readiness after apply. `public-readiness.json`
records `authenticated_acceptance: pending`; Actions never receives account
credentials. The private operator must separately complete authenticated smoke,
real browser/version checks and persistence before deployment acceptance is complete.
Both check shells bind their image and evidence to the requested source and remove
stale success reports on failure.
