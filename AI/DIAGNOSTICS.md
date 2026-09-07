# Content-free operator diagnostics

E07.2 provides Docker operator commands, with no administrator page or public
logging endpoint. These commands do not allocate, prune or rewrite document files.
Use the configured Fillable Compose project; do not run commands against an unrelated
application's services.

```sh
docker compose -f compose.yaml -f compose.prod.yaml exec -T api python -m app.diagnostics status
docker compose -f compose.yaml -f compose.prod.yaml exec -T api python -m app.diagnostics audit --limit 50
docker compose -f compose.yaml -f compose.prod.yaml exec -T api python -m app.diagnostics audit --after <EVENT_UUID> --limit 50
```

`status` reports counts, maximum attempt number and expired leases for each durable
job status, plus physical storage capacity, outstanding reservations, headroom and
whether new writes fit. It never returns job summaries, field snapshots, document
text or file paths. Historical failed jobs remain visible as counts; they do not by
themselves make the command fail. An unwritable capacity result or failed latest maintenance tick exits 1 while still
printing its counters. Successful reads exit 0, unavailable diagnostics exit 1 with
a fixed error code, and invalid arguments exit 2 without echoing argument values.

`audit` returns newest events first, ordered by timestamp and UUID. Pages contain
1–100 events (default 50); pass the returned `next_cursor` as `--after`. New events
ahead of a cursor do not duplicate already-read events. Each page includes only
known action names, timestamps, opaque identities and approved integer counters.
Unknown actions become `unknown_event`; unknown details and malformed identities
are omitted. Database reads use read-only transactions with a five-second statement
timeout. Migration `0012_audit_chronology` adds the matching index and preserves all
events; its downgrade removes only that index.

Successful saves and restores write deterministic `revision_saved` or
`revision_restored` events in the same transaction as the new revision. The audit
contains actor/owner, document/version/parent/restore identities and version number.
A failed transaction has no success event; an exact committed retry does not add a
second event. Existing quota, deletion, retention and reconciliation audits remain
available through the same command. These are operational records, not a claim of
a tamper-proof or compliance audit system.

Unexpected HTTP exceptions emit only the fixed `request_failed` event and the
existing localized `internal_error` response. If a response has started, the server
terminates it with a sanitized exception; the original message and exception chain
do not reach Uvicorn logs. Clients retain their normal uncertain-write retry behavior.

The Fillable gateway logs JSON containing fixed route/method categories, status,
response byte count and duration. It omits raw URIs, query strings, headers, cookies
and uploaded names. Native per-request nginx error messages are suppressed because
they can include those values; categorized 4xx/5xx events remain available. Startup
and explicit `nginx -t` configuration diagnostics remain operator-visible. This
configuration affects only Fillable's gateway, not the shared server nginx.

Verification uses a real Uvicorn server for ordinary, streaming and background
failures, real PostgreSQL for diagnostics/audit/migrations, and actual gateway
stdout/stderr in fresh development and production-style Docker. Synthetic probes
include private-looking URI/query/header/method values and an oversized request.
Development uses Vite's asset fallback; production verifies missing assets return
404. No supplied-server access or deployment is part of this task. Scheduled
reconciliation is described in [Maintenance](MAINTENANCE.md).

`status` also includes the bounded [maintenance state](MAINTENANCE.md), safe per-task
counters and progress timestamps. A failed latest maintenance tick exits 1; stale
`running` records and last-success timestamps remain visible after a process crash.
