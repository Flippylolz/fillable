# Scheduled cleanup and reconciliation

E07.3 runs `python -m app.maintenance` in the Fillable Compose `maintenance` service.
It uses the same Python image, PostgreSQL and private document storage as the API.
It needs neither Redis nor a host cron entry. The service starts after storage
initialization and reviewed migrations; production restarts it unless stopped.
It has a read-only root filesystem, temporary `/tmp`, 256 MiB memory and 0.5 CPU.
No shared-server service or configuration is involved.

Each tick performs bounded storage-operation reconciliation, account reconciliation,
configured historical pruning, read-only unknown-entry inventory, and capacity checks.
The default batch is 20 (allowed 1–100). Three UUID cursors persist in PostgreSQL;
each ordered sweep advances through failed entries and wraps after its last page.
A busy reader or live operation is deferred until a later sweep. Account-lock and
audit-write failures are returned as failures without dropping completed page progress.
A failed whole-task operation is retried at most three times with one- and two-second,
interruptible delays. Other tasks still run. The process waits 60 seconds after each
tick, including a failed tick, so an unavailable database cannot cause a tight loop.

Set `MAINTENANCE_BATCH` or `MAINTENANCE_INTERVAL_SECONDS` in the Compose environment
to change these bounds; the interval must be 10–3600 seconds. PostgreSQL statement
and lock timeouts are 5 and 2 seconds, scoped to this service's connections through
`PGOPTIONS`. Batch size and retries bound work; they are not a guaranteed wall-clock
limit on filesystem operations. SIGTERM/SIGINT stops between tasks or during waits;
an interrupted tick is failed, and unfinished idempotent work can replay safely.

A dedicated PostgreSQL session owns one application advisory lock. Its connection
uses `NullPool`, so closing it physically releases the lock even after exceptions.
Domain work uses separate short transactions. A lost/reconnected guard is rejected;
run UUIDs fence progress writes against a newer runner. Process death releases the
lock. The next tick counts the interrupted run and resumes the last committed
cursors. Duplicate work after a crash still goes through existing file locks,
ownership/reference checks, idempotency and quota accounting.

Migration `0013_maintenance_state` adds only a singleton progress table. It does not
alter document rows or files. Downgrade is permitted before any run, and refuses to
discard populated maintenance history. Preserve this schema during forward recovery.

## Retention and failure visibility

History retention remains **all revisions by default**. A scheduler does not infer
a deletion policy from low disk space or a reduced quota. When an operator explicitly
configures `keep_latest`, scheduled pruning uses the same reviewed retention service:
original/current revisions and shared references remain protected, provenance remains,
and bytes remain charged until unlink succeeds. Unknown filesystem entries are only
reported; they are never deleted. Inventory examines a bounded prefix and reports
`truncated` when incomplete; it is not a claim of a complete filesystem inventory.

Use the existing [diagnostic commands](DIAGNOSTICS.md). `status` includes maintenance
state, run ID, three cursors, start/update/finish/last-success timestamps, interrupted
run count, and per-task attempt/examined/failure/deferred/truncated counters. It emits
no document text, filenames, paths or exception messages. Failed latest-tick state
makes the command exit 1. A later successful batch tick clears that state; this does
not claim that every item in a multi-page sweep was healthy. Inspect timestamps and
service state as well: an unfinished `running` record can remain after process death
until the next scheduler resumes it. No dashboard or notification service is added.

The process logs only fixed `maintenance_tick` events and fixed status names. The
operator can run a single bounded tick through the same singleton gate:

```sh
docker compose -f compose.yaml -f compose.prod.yaml exec -T maintenance python -m app.maintenance --once
```

Exit 0 means successful or another runner already owns the gate; failed ticks exit 1,
and invalid configuration/arguments exit 2. The scheduled process stays alive after
ordinary tick failures and retries on its next interval.

## Verification

Real PostgreSQL tests cover competing schedulers, process death, guard connection
loss, stale run fences, persistent cursor progression past corrupt entries, bounded
lock waits, failed physical deletion accounting, and migration preservation. Synthetic
document tests exercise default all-history and actual scheduled opt-in pruning while
checking original/current DOCX and retained provenance. Unknown bytes stay untouched.
Fresh development and production-style verification observes the actual scheduler
and its connection timeouts. Its temporary retention-policy persistence probe pauses
the scheduler until `all` is restored before browser history fixtures run; pruning
proofs use the explicitly isolated integration database and synthetic storage.
