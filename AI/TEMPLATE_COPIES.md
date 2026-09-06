# Independent template copies

E03.6 adds `POST /api/documents/{id}/copies` with `source_version_id`, a normalized
new title and `Idempotency-Key`. Exact-origin CSRF and an active owner session are
required. The source must be an owned active template at the requested saved revision.
The returned individual document opens in the existing workspace; the previous
workspace's unsaved-draft guard still applies. If navigation is declined, the copy
remains in the Documents tab. The title/copy form and error controls are localized
in Ukrainian and English, and do not clear a separate upload draft.

## Snapshot and storage boundary

The shared storage service allocates a new opaque file, counts/reserves actual bytes
before writing, and atomically commits that file, accounting, a new resource, its
initial version and processing intent. The initial version and original reference
only that new physical file; neither references the template's file. The saved model,
including the current field/control metadata and unsupported-feature counts, is copied
with the saved DOCX bytes. No HTML conversion or text regeneration occurs. E04.2b also clones the completed, validated proposal snapshot into an independent
completed job for the target revision; E06 retention extends the same contract.

A lazy source iterator permits a committed operation retry to return its existing
copy without reopening a source that was subsequently changed or deleted. Its request
fingerprint binds source resource, saved revision and normalized title. Changed payloads
cannot reuse the key. Deleting the resulting document makes that replay unavailable;
it never resurrects a deleted result. An ambiguous response retains the key; a
terminal aborted/conflicting/admission rejection requires a new attempt. A new request
uses a verified, size-bounded immutable source file, and rechecks the active session
and locked source revision before commit. A source change/deletion during copying
aborts and cleans up the target, leaving no retained target or quota reservation.

Copy buffering shares the two-slot upload admission bound. Processing admission and
quota/capacity failures preserve the source and use the same durable cleanup path.
The response is typed and no-store; diagnostics contain machine codes only. This
feature creates one independent saved snapshot, not a live link or a copy of unsaved
editor state. Production saves and history remain E06.

## Verification

Real PostgreSQL/filesystem tests use an exported and reopened edited DOCX revision,
verify byte/model equality and distinct files, source deletion and changed-source
replay, concurrent duplicate delivery and exact charges, owner/CSRF/kind/revision
checks, quota failure/cleanup, source changes between read and finalization, and safe
failure diagnostics. Frontend tests cover localized title preservation, cancelled
forms, validation, disabled/pending requests, ambiguous retry keys, terminal retries,
changed payloads and unmount cancellation. The desktop/mobile browser flow deliberately
loses a successfully committed copy response, retries once, opens the independent
workspace, verifies one quota charge, deletes the source, and downloads/reopens the
remaining copy. Full source edits/restoration after copying will be covered by E06.
