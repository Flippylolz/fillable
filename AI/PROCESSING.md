# Durable saved-document processing

E03.5a supplies processing intent, status, dispatch and execution. E03.5b connects
initial upload intent and the library polling controls. The first processor inspects
supported controls, paragraph counts and unsupported-feature counts in verified saved
DOCX bytes. It does not claim field completion or implement E04's placeholder/blank
candidate discovery, and it does not modify the saved model or create a retained file. E04.2b extends
inspection with durable validated native/explicit-token proposals; see [Field discovery](FIELD_DISCOVERY.md).

## Durable state and APIs

Migration `0006_processing_jobs` adds a unique job per document/saved revision with
an ownership-constrained version FK, state, attempt budget, lease, timestamps, safe
failure code and integer summary. Downgrade refuses to discard existing jobs.
`POST /api/documents/{id}/processing` requires exact-origin CSRF and an active owner
session inside the transaction. It returns existing live/completed work idempotently;
an explicit failed-job retry gets a new attempt number and a fresh three-attempt budget.
At most five queued/running jobs per owner may be admitted. `GET` on that path reads
the owned current revision's status. Both use no-store responses. Deleted/foreign
resources cannot be submitted or polled. Initial uploads commit intent in the same
transaction as the resource, initial version and file/quota finalization. Admission
limits abort the upload cleanly; the UI preserves the draft and uses a new operation
key after a definitive capacity rejection. Ambiguous network retries retain the key.

The PostgreSQL row commits before any Redis dispatch. RQ contains only a job UUID and
attempt number using JSON serialization; document content, paths, names and credentials
are never queued. Redis is replaceable transport. A small non-root Python dispatcher
service visits at most 100 pending/expired records per batch, cycles every five seconds,
and reconstructs missing deliveries. It stops the batch after a Redis connection error.
The service has no document filesystem mount and exposes no host port.

## Execution and recovery

RQ executes each inspection in its worker process with a 30-second job timeout.
A PostgreSQL claim lasts 45 seconds. Claim/finalization lock resource then job, check
active ownership/resource state and the source revision, and reject obsolete attempts.
Finalization rejects an expired lease. Stale/deleted/inactive-owner work cannot publish
results. The shared storage reader verifies actual bytes/digest, then upload validation
applies compressed/expanded/XML/deadline limits. Integer counts and the E04.2b validated proposal snapshot are retained in the owned
job; original bytes, editor models and quota usage stay unchanged. Proposal text is
cleared on resource deletion, independently of any copied result.

Processing exceptions become `processing_failed` without passing their text to RQ.
Normal failures and expired running leases consume bounded attempts. Dispatch also
recovers deliveries that finish/fail or remain started past the deadline before the
business claim; they cannot remain queued indefinitely or retry without consuming the
budget. A lost result/duplicate delivery cannot overwrite another attempt. Database
interruptions leave durable intent/lease for recovery. Dispatch logs contain counts or
machine codes, not exception strings. Worker job-description logging remains disabled.

This dispatcher handles processing delivery only. General storage cleanup scheduling,
capacity diagnostics and retention remain E07/E06. Historical version pruning must
respect or explicitly retire processing references before removing version metadata.

## Library status

The library distinguishes saved bytes from inspection state in both UI languages.
Each visible resource polls its current revision every two seconds while queued or
running; terminal states stop polling. Requests/timers are cancelled on unmount or
revision replacement, and obsolete results cannot replace a newer revision status.
A failed status request preserves the known state and offers a status retry. Failed
inspection and legacy uninspected revisions offer an explicit CSRF-protected submit.
Background checks do not block navigation or clear upload/editor drafts. Pending
deletions have no processing controls.

## Verification

Real PostgreSQL/Redis tests cover owned/idempotent status, JSON payload/timeout, worker
completion, unchanged file/quota state, Redis outage/lost delivery reconstruction,
normal/pre-claim/lease failure budgets, explicit retry, old-attempt and expired-result
rejection, source/deletion/owner fences, duplicate concurrent delivery, admission and
safe diagnostics. The isolated Docker verifier invokes `verify_processing.py` against
the actual dispatcher and forked RQ worker, checks success and unchanged bytes/usage,
then verifies durable state after development-to-production recreation. All fixture
accounts/data belong to explicit QA provisioning, not ordinary application startup.
