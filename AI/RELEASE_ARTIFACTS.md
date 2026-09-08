# Verified release artifacts — E08.2

The manual `.github/workflows/deploy.yml` accepts the full current protected-main
commit. Its credential-free verification job requires the latest push CI run for
that exact revision, the expected active workflow identity, and successful
`ci-required` plus every job it aggregates (`lint`, `backend-tests`,
`frontend-tests`, `browser`, `development`, `contracts`, `upgrade-checks`) from
the same completed run attempt. Missing,
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

D024 HTTPS port 3200 and the existing shared-nginx owner are the accepted target. No
application is deployed by introducing this workflow. Contract tests exercise rejected
CI states and races, archive tampering, unsafe/duplicate entries and image identity
mismatches; actual image archive and workflow evidence are recorded in the epic ledger.

E08.7 adds credential-free public readiness after apply. `public-readiness.json`
records `authenticated_acceptance: pending`; Actions never receives account
credentials. The private operator must separately complete authenticated smoke,
real browser/version checks and persistence before deployment acceptance is complete.
Both check shells bind their image and evidence to the requested source and remove
stale success reports on failure.

E08.9 keeps version-1 manifest IDs as config digests. The archive verifier also returns
an OCI manifest digest only after checking its bytes, size, media type, exact config
reference, source tag and annotations against that same release. No arbitrary alias,
nested index or unchecked descriptor becomes an accepted runtime identity.

The receiver tries only those verified immutable digests. Classic Docker resolves the
config ID; the target's containerd store resolves the OCI manifest ID. The inspected
ID must equal the selected candidate, with the same Linux amd64 platform and full
source revision. Missing or mismatched metadata fails closed. Compose and private
`state.json` use the resolved host identity; the public artifact manifest and archive
digest remain unchanged. Later account and recovery checks compare the running
container to that recorded host identity. Never change Docker's storage driver or
substitute a mutable tag to make rollout pass.

This distinction was reproduced using real saved classic-store images and the actual
already-imported target OCI images. Docker documents the [containerd image store](https://docs.docker.com/engine/storage/containerd/)
as a separate storage backend; the exact identity behavior above is observed evidence
from the two engines used by this release path.
