# Local storage and per-user quotas

E03.3's [document persistence](DOCUMENT_PERSISTENCE.md) uses the storage finalization
transaction for owned resource/version metadata. An upload's original and initial
revision share one immutable file charged once. Subsequent versions and template
copies must allocate their own retained files; this does not authorize cross-document
sharing or mutation of the original.

Status: proposed detailed design implementing accepted decisions D003 and D004.

## Configuration and accounting

An administrator manages a global default allowance and optional overrides per user. Store all accounting values as integer bytes. The UI can display human-readable units with explicit rounding.

For MVP, administration uses containerized operator commands. Users see read-only usage/allowance in the library and profile. A separate administrator page is deferred by D011.

- `quota_override_bytes = null`: inherit the current global default.
- `quota_override_bytes = 0`: no capacity for additional stored bytes.
- Positive override: that user's explicit allowance.
- Negative limits are invalid. Unlimited accounts are outside v1.
- `used_bytes`: files charged to the user that have not been physically removed and reconciled.
- `reserved_bytes`: capacity held by in-progress operations.

```text
effective_limit = override if present, otherwise global_default
available_bytes = max(0, effective_limit - used_bytes - reserved_bytes)
```

Changing an inherited default affects users without overrides. Audit administrative changes. Lowering a limit below usage never deletes documents automatically. It prevents new allocations; existing downloads and deletions remain available.

## What counts

| File category | Accounting |
| --- | --- |
| Original upload | Charged to owner |
| Reusable template and its saved field-bearing DOCX | Charged to owner |
| Independent document created from a template | Reserve and charge the new copy to its owner |
| Current saved DOCX | Charged to owner |
| Retained historical version | Charged to owner |
| New revision created by restoring a historical version | Reserve and charge the new file; existing retained versions remain charged |
| Retained export or preview | Charged to owner |
| Files pending deletion | Still charged until physical deletion |
| A download of an already stored file | No extra charge |
| In-progress upload or retained output | Reserved before/during writing; charged after commit |
| Transient conversion, parsing, or download output | Separate bounded temporary allowance; automatically cleaned |
| Database, Redis, logs | Server operating capacity, outside the user document allowance |

Charge logical file bytes rather than filesystem block allocation. Charge each stored file once even if several records reference it; a separate physical copy is a separate charge. V1 does not deduplicate across users. Temporary space and operating data still need server-wide capacity management; a user quota is not a guarantee that the physical disk has room. Backups are excluded from MVP under D018. Retained document versions remain required and charged; they are not independent backups.

Define explicit operator retention settings for versions and generated outputs before enabling automatic pruning, and display the policy in version history. Never silently discard history just to make a failing write fit. An autosave or restore may consume version space, so show impending quota exhaustion before the user believes a save succeeded. A trash browser is deferred; any future trash feature must continue charging retained bytes until physical removal.

## Filesystem layout and access

Use server-generated opaque identifiers under the configured storage root, for example:

```text
<storage-root>/files/<owner-id>/<file-id>
<storage-root>/staging/<operation-id>
```

Original filenames are metadata, not paths. Prevent traversal and symlink escape. User files are outside the webroot and accessible only after ownership checks. API and worker containers share the mount and storage implementation.

## Write protocol

1. Authenticate, authorize, and validate the operation. Assign an idempotency key bound to its owner and purpose.
2. Atomically lock/recheck account capacity and reserve bytes in PostgreSQL. Serialize allocation against both per-user override changes and global-default changes so no request uses a stale limit.
3. Check actual disk headroom and temporary limits. Stream into a bounded staging file. Do not trust `Content-Length`; count bytes received. Reserve additional chunks before writing them if the final size is unknown.
4. Validate the completed file and compute its size and digest. All generated artifacts, including worker outputs, follow the same allocation rules.
5. Recheck the current quota and source revision before finalization. A quota reduction may require aborting an in-progress new allocation.
6. Move the complete file to its final location atomically on the same filesystem. Commit the file/version records and matching field snapshot, convert reservation to actual usage, and mark the operation committed.
7. Expose the new version only when its file and metadata are complete. Release excess reserved capacity and report success.

PostgreSQL and filesystem changes are not one atomic transaction. Persist an operation state machine, for example `reserved -> writing -> staged -> committed` with cleanup/recovery states. Recovery must inspect both records and files and resume or clean up safely. Do not assume rollback undoes a file move.

For a retained replacement/version, reserve the full new file while the old version still exists. Do not subtract the old size until its bytes are actually removed under the retention/deletion policy.

## Failures and deletion

- Duplicate retries return the existing result or continue the same operation; they do not charge twice.
- On failure, remove partial or orphaned output before releasing its capacity. If cleanup fails, retain accounting and retry cleanup.
- Reservation leases require active-owner heartbeats. Recovery checks operation liveness before expiring a lease; do not free capacity still used by a running writer.
- Staging cleanup must be safe against active writes and resumable after crashes.
- Permanent deletion marks files pending removal, removes the bytes, then finalizes accounting. It is idempotent across crashes.
- Deleting a template must not delete documents created from it or release capacity charged to those independent copies.
- A history restore uses the same reservation and commit protocol as a save. Quota failure preserves the current version and selected historical version.
- Periodic reconciliation compares file records, reservation states, and actual files. Report and repair discrepancies with an audit trail rather than silently hiding them.
- Global disk exhaustion produces a different error from a user's quota exhaustion.
- Failed save UI preserves the working draft and does not show a saved indicator. Offer a download/retry path where feasible without bypassing bounded processing limits.

## API and UI requirements

- User usage response includes limit, used, reserved, available, and over-limit state.
- Operator commands support changing the default and an override, and resetting an override to inherited, through the shared service. Do not add an administrator screen for MVP.
- Enforce quota in the service layer, not only the upload route or UI.
- Give distinct machine-readable errors for quota exceeded, upload too large, disk capacity unavailable, and stale revision. Agree concrete HTTP status codes in E02.
- Never expose physical server paths in API responses.

## Required integration evidence

Use real PostgreSQL and a bounded test storage directory, with deterministic fault injection where needed.

- Inheritance, overrides, zero limit, and invalid configuration.
- Changing a default versus a user override, including while allocations are active.
- Exact-limit success and over-limit rejection.
- Two concurrent operations whose combined size exceeds available capacity: at most one may reserve the conflicting capacity.
- Unknown-size input and input whose declared length is incorrect.
- New versions, exports, previews, and repeated retries use the same accounting path.
- Creating a document from a template reserves the copy's capacity and is idempotent; deleting the source leaves the copy and its accounting intact.
- Restoring a historical revision accounts for its new copy once and preserves current/history state on failure.
- Worker crash and recovery around file move, database commit, and reservation release.
- Confirmed deletion, deletion of a source template, and failed physical cleanup.
- Quota reduction below usage preserves files and blocks new allocations.
- Temporary capacity and disk-headroom failure, without lost originals or false save success.
- Storage usage remains correct across container restarts and reconciliation.

## E02.2 schema contract

The initial inherited default is 1 GiB (1,073,741,824 bytes), stored once in the
singleton `storage_settings` row. This is an allocation limit, not a promise of
physical disk capacity; E02.3 checks initial headroom and E02.4 expands capacity
configuration. Operator quota changes are E02.5.
Amounts are exact integer bytes from 0 through 9,007,199,254,740,991, within both
PostgreSQL integer storage and JavaScript's exact integer range. Unlimited values,
negative amounts, booleans and fractional configuration values are invalid.

`storage_accounts` has one owner-bound row, nullable override, used and reserved
counters. Existing users are backfilled with inherited zero-usage accounts because
no retained user-file writes existed before this migration. Future provisioning
creates user/account rows in one transaction. Counters are not constrained to the
current limit: quota reduction must preserve charged/reserved bytes and report
an over-limit state. `calculate_usage` distinguishes null inheritance, zero override,
exact capacity and over-limit availability without changing stored counters.

`storage_reservations` records owner, opaque operation/file IDs, owner-scoped
idempotency key, request fingerprint, purpose, allocated/written/expected bytes,
lease token/deadline and timestamps. Allowed states are `reserved`, `writing`,
`staged`, `committed`, `cleanup_pending`, `aborted`. Purpose identifies the retained
original/template/document/version/export/preview; copies/restores use the same
applicable purpose and reservation path. The unique owner/key contract prevents a
retry creating another allocation; the service must reject conflicting request
fingerprints/purposes. Written bytes cannot exceed allocated bytes.

`stored_files` has a unique reservation, exact size/digest and `staged`, `ready`,
`pending_delete` or `deleted` state. A composite foreign key binds the result ID and
owner to its reservation, preventing cross-owner result links. Ready/deleted states
require their timestamps; digests are lowercase SHA-256. Opaque IDs determine
server paths later; physical paths and original filenames are not quota keys.
Rows remain as idempotency/recovery records after physical deletion. Restrictive
foreign keys prevent owner/reservation deletion from silently losing file metadata.

The migration can roll back only before reservations/files, charged bytes or custom
quota settings exist. Otherwise it refuses to drop storage metadata; release
recovery must preserve data. These schema constraints are not yet the write service:
E02.3 enforces lock ordering, streaming reservation, state transitions and atomic
file/record finalization and per-operation recovery; E02.4 adds deletion, batch
cleanup/reconciliation and capacity configuration.
No retained file is written by E02.2 and no quota enforcement is claimed from models
alone. Required PostgreSQL tests cover invalid values, identity/owner constraints,
backfill, repeated upgrades, over-limit preservation and guarded rollback.

## E02.3 enforced write and recovery protocol

`app.storage.service.Storage` is the single retained-write implementation for API,
worker and maintenance callers. It accepts an authorized owner UUID, owner-scoped
idempotency key, validated request/source fingerprint, purpose and byte iterable.
Original filenames never enter a filesystem path. Known sizes reserve before
opening staging; unknown sizes reserve each bounded 64 KiB slice before writing.
Actual bytes and SHA-256 are counted; a false declared length aborts. The initial
processing policy limits each file to 10 MiB, active allocated staging to 64 MiB,
and preserves 64 MiB of physical disk headroom. E02.4 exposes operational capacity
configuration and batch reconciliation; these checks already apply to every write.

The lock order is singleton settings, owner account, then reservation/file. Quota
configuration must use that order too. Each allocation and finalization reads the
current inherited/override limit, so reductions preserve old files and may abort a
new in-flight write. Physical checks include outstanding allocated-but-not-written
promises across all active reservations; written counters advance only after the
bytes were written, making crash uncertainty conservative. OS disk exhaustion is
reported separately from user quota exhaustion. No caller role bypasses this path.

Publication uses an exclusive same-filesystem hard link from a fully fsynced,
read-only staging inode into `files/<owner>/<file>`, followed by directory fsync.
The staging link stays until SQL commits. It proves inode ownership for abort
cleanup: a pre-existing final-path collision is neither overwritten nor removed.
File readiness, reserved-to-used accounting and an optional DB-only document/revision
finalization callback commit in one SQL transaction. The callback must not commit
independently or perform external side effects. Future saves use it to validate the
source revision and attach the matching file/field snapshot. No file becomes readable
through the service before that transaction succeeds. Reads enforce owner, ready
state, regular-file type, size and digest; files are outside the static webroot.

Every writer holds a nonblocking OS flock throughout its operation. Zero-byte lock
files remain to avoid replacing an inode still locked by another process. UUID-only
paths, directory descriptors and no-follow opens reject symlink escapes; special
files cannot block a read or lock. The one-shot Docker `storage-init` creates and
sets ownership on only the Fillable root and its immediate `files`, `staging` and
`locks` directories. It never recursively changes existing files or unrelated paths.
API and worker both run as UID 10001 and wait for that initialization.

A committed retry returns its existing result without consuming the input stream,
rerunning the callback or charging again. A conflicting fingerprint/purpose/declared
size fails. An active operation reports in-progress without acquiring the creating writer’s
filesystem lock; an aborted attempt is terminal
and requires a new key. A committed result that was later deleted is not recreated.
A failure after SQL commit (including a lost response) cannot clean the retained file.
The redundant staging hard link may survive; it adds no second logical byte charge.

Uncommitted failures enter `cleanup_pending`; filesystem removal and directory fsync
must succeed before reserved capacity is released and the operation becomes `aborted`.
Failed cleanup retains its reservation. Recovery requires both an expired lease and
an acquired OS lock; a live writer with a stale heartbeat cannot lose its capacity.
Recovery aborts uncommitted output, including a fully published staged file, rather
than inventing a saved revision without matching document metadata. Repeated recovery
is safe after filesystem removal or SQL commit. Committed recovery removes only the
redundant staging link. Batch scheduling, retained-file deletion and reconciliation
reports are E02.4; HTTP upload/download integration follows in E03.

PostgreSQL/filesystem tests exercise exact/inherited/zero quotas, concurrent conflicting
reservations, active locks with expired leases, unknown and false declared sizes,
quota reduction mid-write, callback rollback, short writes, actual ENOSPC, cleanup
failure, symlink/collision protection, corrupt reads and lost responses. A real child
process exits immediately after publication; recovery removes that uncommitted file
and releases its reservation once. The fresh Docker verifier additionally writes
synthetic data through the API container's shared service, reads it from the worker,
recreates development as production, and checks immutable bytes/accounting from both.

## E02.4 deletion and maintenance

`app.storage.maintenance.delete_file` authorizes owner/file identity and permits a
DB-only domain authorization callback when first marking a ready file pending.
That transaction records deletion intent; used bytes remain charged. Deletion takes
an exclusive operation lock, removes both final and any redundant staging link,
fsyncs both directories, then marks deleted and decrements usage in one transaction.
Repeated deletion is a no-op. A crash after unlink leaves a charged pending record
that reconciliation can finish once; failed cleanup never frees its capacity.
Readers hold shared operation locks for the whole stream and recheck readiness
after acquiring them. Deletion reports busy while a download is active. Deleting
one independent file never removes another stored copy or original.

`storage_audit` records lifecycle/maintenance action, optional owner/actor UUIDs,
exact counters/opaque IDs and timestamp. Details reject free-form strings and do
not include document copy, filenames or paths. Deletion intent/completion, recovered
operations, failed reconciliation, counter discrepancies and unknown inventory
entries are auditable. The migration creates an empty table without modifying
files/counters; downgrade refuses to discard populated audit history. Operator quota
changes reuse this audit mechanism in E02.5.

Run one-shot maintenance through the container, for example locally:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.maintenance capacity
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.maintenance reconcile --batch 100
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.maintenance accounts --batch 100
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.maintenance inventory --batch 500
```

`reconcile` processes at most 100 reservation records by default (maximum 500),
returning `next_cursor`; pass that UUID as `--after` to continue. It finishes pending
deletion, aborts expired unlocked staging operations, checks ready file integrity
and cleans redundant committed links. Active locks/leases report busy. Missing or
corrupt ready files report failure and stay charged. `accounts` pages all storage
accounts, including owners without operations. Counter repair can raise an undercount
to the known ready/pending/active totals, but it never reduces an unexpected overcount
from metadata alone: that reports `repair_required` and preserves capacity until
physical investigation. Ordinary safe deletion/abort remains the release mechanism.

`inventory` examines a bounded total of staging entries, owner directories and
retained entries. It reports unknown entry counts and truncation, without returning
names or deleting unknown files. Its bounded read-only scan is observational during
concurrent writes; repeat a discrepancy check before investigation. Inventory does
not follow symlinks or authorize deletion of unrecognized content. The operation
and account cursors provide complete database traversal; inventory truncation is
explicit rather than a claim that the entire disk was checked.

Commands emit JSON with machine codes, IDs and counters. Failures/repair-required
results return nonzero; busy work is retryable. These are storage-operation recovery
primitives for API/worker callers. Durable document jobs/outbox arrive in E06 and
periodic scheduling/bounded scheduled retries in E07.3. No successful document job
or saved field revision is invented by storage cleanup. Parser/export processing
currently stays in bounded memory; this task cleans retained-write staging and does
not introduce an unaccounted generic temporary-file API or automatic history pruning.

Both API and worker receive the same exact integer operational configuration:
`STORAGE_FILE_BYTES` (initial 10 MiB, cannot exceed the parser's 10 MiB ceiling),
`STORAGE_STAGING_BYTES` (64 MiB), `STORAGE_DISK_HEADROOM_BYTES` (64 MiB), and
`STORAGE_LEASE_SECONDS` (60, valid 1–3600). Invalid values fail configuration rather
than silently falling back. Byte settings are bounded by the exact integer range;
zero can disable capacity. `configuration.configured()` constructs the shared service
for runtime callers. `capacity` reports a point-in-time physical-headroom snapshot,
not a reservation or a promise that a later write will fit. The reservation path
continues serializing current quota, staging limits and outstanding disk promises.

Tests cover owner isolation, shared readers/exclusive deletion, callback rollback,
failed physical cleanup, a real process exit after unlink, surviving staging links,
retries, bounded cursors, corruption/unknown-file preservation, conservative counter
repair, audit migration/guard, invalid settings and private CLI output. The fresh
Docker verifier stores an original plus independent copy, deletes the copy twice,
recreates the stack, and verifies original bytes/accounting from API and worker.

## E02.5 usage and operator allocation commands

`GET /api/storage/usage` requires an authenticated active account and always reads
that account's current quota. It returns exact integer `limit_bytes`, `used_bytes`,
`reserved_bytes`, `available_bytes` and boolean `over_limit`, with `Cache-Control:
no-store`. A single joined database read provides the inherited default/account
snapshot. There is no owner selector or HTTP quota-mutation route. The generated
OpenAPI/TypeScript contract includes the response; profile/library presentation
follows in E02.6/E03.1.

Quota changes require trusted operator access to execute a container command, using
the same boundary as account provisioning. A web user's role or request cannot
invoke these commands; there is no administrator screen or artificial `--admin`
flag. Examples for a local stack, using the intended existing account login:

```sh
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.quota_cli default --bytes 1073741824
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.quota_cli override --login document-user --bytes 2147483648
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.quota_cli inherit --login document-user
docker compose -f compose.yaml -f compose.dev.yaml exec -T worker python -m app.storage.quota_cli show --login document-user
```

`default` changes the singleton inherited allowance and increments its revision;
explicit overrides retain their values. `override` sets a specific allowance, and
`inherit` restores null inheritance. Zero blocks additional bytes. Values must be
exact integers in the documented range; negative, fractional, boolean or oversized
service inputs fail. The CLI requires action-specific arguments, looks up an existing
canonical account login and returns JSON counters/status without printing credentials,
login names or file paths. Failure is nonzero; it never provisions a missing user.

`quotas.set_default` and `set_override` serialize against allocations using the same
settings-first lock order. A current setting is read under lock; no-op requests
leave revision/audit unchanged. Actual changes and their `storage_audit` record
commit together, recording previous/new integers or null, owner where relevant,
and global revision. Actor null identifies trusted container-operator execution;
it does not claim an authenticated web actor. Limits never change used/reserved
counters or remove files. Reducing an allowance below retained use leaves downloads
available, returns over-limit usage and can abort an in-flight new write at finalization.

Tests use real sessions for two accounts, verify read-only owner-scoped usage,
no-store responses and exact byte arithmetic, exercise all commands and audit
transitions, observe a real PostgreSQL lock wait, and invoke the actual setters
mid-stream while preserving the original. Fresh Docker verification changes the
synthetic default, sets zero override, proves a retained write is rejected without
losing the original, restores inheritance/default, and checks the authenticated
usage endpoint in desktop/mobile browser flows. No server access is needed.

E06.2c saves each retained revision through the same storage transaction and charges
its actual independently stored DOCX bytes, including review-only changes. It never
overwrites the original or deletes history to make a save fit. The bounded in-memory
JSON/export preparation is not a retained file allocation; its request/model/package
limits and two-request admission are explicit. Quota, physical capacity, owner,
current revision and editing lease are checked again at the final commit boundary.
A lost commit response replays the exact committed revision without a second charge.

## E06.6 historical restore accounting

A restore copies the exact selected retained file into a separately charged immutable
version through `Storage.store`, using the `restore:` operation namespace. It does
not reuse an existing file reference to evade the new-version allowance. Preparation
verifies the selected file/model pair; the final transaction shares save's active
session/lease/current checks and rechecks selected retention under the account lock.
Quota reduction, disk failure, stale authority or a removed selection cannot publish
a partial current revision. A lost response replays the exact committed version
without allocating again, even when current has advanced. Deleted results are never
recreated by replay. Parent/restored-from metadata is retained separately from bytes;
E06.5 pruning preserves provenance and charges pending physical cleanup.


### Explicit history retention

The [history policy](HISTORY.md#operator-retention-e065) defaults to keep-all. Only an
explicit operator limit enables eligibility for bounded pruning; quota changes and
failed saves do not call it. Originals/current files remain protected. Each removal
rechecks policy and resource state under locks and uses `delete_file`, so bytes remain
charged through pending deletion and are credited only after unlink. Failed cleanup
uses existing reconciliation. Pruning clears saved content/review/job snapshots while
retaining opaque provenance metadata. Scheduling follows in E07.3.


E06.7 autosaves use the identical revision-save storage transaction as manual saves.
Each retained autosave reserves and charges the full new file. The local workspace
toggle explains this usage, and a quota/disk/save error keeps the draft and stops
automatic retry until explicit recovery. No autosave calls retention or silently
replaces older charged files. Lost-response retries reuse the exact operation;
newer edits are saved separately only after that outcome is acknowledged.
