# Local storage and per-user quotas

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
