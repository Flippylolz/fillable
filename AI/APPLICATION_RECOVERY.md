# Full-application restart and upgrade verification

E07.4 extends initial-upload persistence checks to edited, reviewed, independently
copied and restored documents. The executable proof is
`scripts/verify-application-recovery.sh`; run it from the repository after staging
all intended changes. It captures the Git index as one immutable tree and executes
its own staged driver from a frozen launcher. Later index edits cannot change the
running proof. Git history must contain the pinned previous source commit. Docker is the runtime; no host Python is required.

The baseline is merged PR #64, commit
`191282ce485d6f562be0cd8d0a8b183b7e2ebb1d`, with schema `0012_audit_chronology`.
The driver builds that application's production-style images, then builds the staged
current application and upgrades the same PostgreSQL and document storage to
`0013_maintenance_state`. This tests that specific previous-image migration path;
it does not claim arbitrary old releases or destructive downgrades are supported.

Each run creates a unique temporary directory and Compose project and refuses an
existing project container/volume namespace. A database marker, fixed internal QA
origin and dedicated synthetic account guard the probe. Only this project's services
are stopped or recreated. All volumes, the verification tree and reports are retained.
The probe streams its code and committed synthetic fixtures into writable `/tmp`;
application root filesystems remain read-only. It does not enable the prototype API.

The scenario saves a Ukrainian reviewed template as revision 2, creates an independent
copy and edits that copy, restores the template's original as revision 3, then restores
the reviewed revision as revision 4. It checks all retained histories through the API,
PostgreSQL metadata and actual private storage reads. Its assertion manifest contains
opaque identifiers, provenance, byte counts, quota counters and SHA256 hashes of
canonical model/review JSON and downloaded bytes. It is synthetic test evidence,
not a backup or an application-data recovery mechanism.

After the image/schema upgrade, the probe compares the entire manifest. Exact source
badges are checked in desktop/mobile browsers against both old and new artifacts.
The current artifact uses its commit when the captured tree matches HEAD; an
uncommitted staged snapshot uses the specified `development` fallback. Both the
source tree and commit/fallback are retained in the reports.
Originals, paired field review, later retained versions, source/copy independence,
owner IDs and quota totals must remain unchanged.

The crash phase stops the isolated maintenance service, creates one extra synthetic
resource, and calls the real authorized domain deletion service in a child process.
The child exits immediately after real unlink and before accounting credit. The probe
requires durable pending metadata, absent physical bytes and the still-charged amount.
A full stack restart then starts the actual scheduler; its reconciliation must restore
the baseline quota while the retained documents still match the manifest. This is a
real process crash at one explicit database/filesystem boundary, complemented by the
existing storage crash integration tests. It is not a disk-loss or backup/restore drill.

CI runs this proof in mandatory `upgrade-checks`, separately from the existing full
browser/backend/frontend/raw coverage checks. `ci-required` requires both job results
to be `success`; missing, failed, skipped or cancelled results cannot satisfy it.
Reports are retained as `application-recovery`. No workflow deploys to a server here;
E08 remains last after all E07 acceptance work is verified and merged.
