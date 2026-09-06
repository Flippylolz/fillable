# Owned document persistence

E03.3 stores uploaded templates and one-off documents through the shared storage
service. E03.1 supplies the library/upload UI; E03.4 supplies download/open/delete
operations; E03.5 supplies durable processing jobs. Upload success means a committed
saved revision, not completed field analysis or a filled document.

`POST /api/documents` accepts raw DOCX bytes with DOCX or octet-stream content type.
It requires the existing session, exact Origin, CSRF token and an `Idempotency-Key`
(1–120 ASCII letters/digits or `._:-`). `X-Upload-Metadata` is at most 4096 characters:
base64-encoded UTF-8 JSON containing only `kind` (`template`/`document`), `filename`
(up to 255 characters) and `title` (trimmed, nonblank, at most 160 characters, no
control characters). Names/titles are not URL query parameters. Base64 is transport
encoding, not encryption; the accepted public HTTP scheme remains unchanged.

A process-local two-slot admission semaphore is acquired before reading the body.
The handler checks declared and actual bytes against 10 MiB, rejects inconsistent
lengths, and bounds body receipt to 30 seconds. It does not use multipart temporary
file spooling. Validation/storage run in the existing worker-thread facility; the
slot remains held through completion and is released on errors. DOCX admission uses
[the E03.2 validator](DOCX_VALIDATION.md); invalid packages never reserve retained
space. These limits are per API process; operational process limits remain E07.

The private gateway allows up to 24 MiB for API requests (including the opt-in editor
proof), disables request-body buffering, and uses HTTP/1.1 upstream streaming. The
production upload handler still enforces 10 MiB. Gateway 413 errors use the same
machine-readable envelope and `no-store`. Gateway access logs contain method/path/
status without queries; API access logging is disabled. Neither bodies nor metadata
headers are logged. SQL storage failures return a generic recoverable code.

## Commit and retry contract

The upload fingerprint binds normalized metadata and the original bytes' SHA-256.
The shared storage key is scoped to owner and prefixed `upload:`. Original bytes are
written once and made immutable through the storage service. Its final SQL callback
rechecks the active account/session and inserts the document plus initial version
in the same transaction as file readiness and quota accounting. A failure rolls back
metadata and cleans retained bytes before releasing reservations; existing recovery
handles process/database/filesystem crash boundaries.

The initial version and original reference the same immutable physical file, charged
once. Subsequent editing must allocate another immutable file and leave the original
intact. Initial metadata includes resource kind/title/filename, version number 1,
source-derived editor model, unsupported-region count, timestamps and file identity.
The file record holds exact size/digest. Field analysis remains explicitly
`not_started`; no invented field schema or completed job is recorded.

Retrying the same owner/key/content returns the same resource/version and does not
write another file or charge again. Different content conflicts. An active write
returns `operation_in_progress`; a definitively aborted attempt requires a new key.
Resource IDs derive from the storage result UUID and are stable on committed retries.
The session is rechecked before validation, in finalization, and before returning a
retry result. A commit that succeeds before a session is revoked remains saved;
a later authorization failure does not delete committed user work.

## Schema and reads

Migration `0005_documents` adds documents and immutable version records plus a
composite stored-file ownership key. Composite foreign keys enforce file owner,
version owner and the document's current version identity. The current-version
constraint is deferred to transaction commit to permit the atomic initial pair.
The migration preserves existing users/files/accounting; downgrade refuses populated
document/version tables and never deletes their data.

`GET /api/documents?kind=template|document&limit=1..100&cursor=<id>` returns owned
active saved records ordered by creation time and UUID, with a bounded next cursor.
`GET /api/documents/<id>` returns owned saved metadata. Both require authentication
and use `no-store`. Other owners receive no records/404, and invalid or foreign list
cursors are rejected without exposing metadata. Physical paths, password/session
hashes and document model contents are absent from these summary responses.

## Verification

Real PostgreSQL/filesystem/API tests cover both kinds, immutable original bytes and
matching initial model, exact single charging, committed retry, changed-content
conflict, concurrent in-progress retry/hidden partial resource, owner isolation,
bounded pagination, quota/format rejection, callback rollback, database constraints,
empty upgrade/downgrade, and body/admission failures. The synthetic Docker verifier
uploads through the gateway, retries, recreates the stack, reads metadata through
the API and verifies original bytes from both API and worker. It also sends malformed
input larger than 1 MiB to prove it reaches the bounded validator. The verifier is
explicit QA only and provisions no account during normal startup.
