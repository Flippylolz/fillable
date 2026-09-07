# Saved revision history

E06.3a implements owner-scoped metadata and preview APIs for templates and documents.
E06.4 adds exact historical downloads; restore is E06.6 and the complete in-workspace panel is
E06.3b. The current manual-save editor remains the working-document authority.

`GET /api/documents/{identity}/versions` returns `current_version_id`, newest-first
`items` and optional `next_before`. Each item contains the selected revision ID,
number, timestamp, exact saved byte size/digest, unsupported count and current marker.
It does not return document text or field review in the list. `limit` defaults to 50
and is bounded to 1–100. Pass the returned version number as `before` for the next
page; positive before-numbers are scoped to the owned document. An empty page is a
successful empty list, while a missing, deleted or unowned document returns 404.

The page and current marker share a PostgreSQL repeatable-read snapshot. A concurrent
save cannot mix old current metadata with newly committed rows inside one page.
Subsequent pages/refreshes use new snapshots; a new save may appear above an earlier
cursor and is available on refresh. Historical files remain unchanged.

`GET /api/documents/{identity}/versions/{version}/content` selects the exact owned
revision within that document and returns `version` plus its combined document/model
and field-review snapshot. It never resolves the selected ID to the current version.
The reader verifies the immutable saved file before returning the pair. Missing,
corrupt or over-bound files fail explicitly; there is no fabricated successful
preview or reparsing that replaces the persisted source identities.

Both routes require an active authenticated owner and return `Cache-Control: no-store`.
Preview shares the bounded two-reader admission with current reads/downloads and
uses the existing verified storage reader. Metadata listing does not hash every
historical file; opening a selected revision verifies that file. Neither API creates
retained preview files, modifies a document or lease, triggers processing, or changes
quota usage. List and preview failures use existing localized machine-code contracts.

Originals and saved history remain retained. Configurable pruning is E06.5 and must
preserve original/current data, coordinated readers/restores, provenance and accounting
until physical cleanup. No history is removed to make a failed save fit.

Integration tests cover both resource kinds, exact original/edited/review-only pairs,
owner/resource/revision isolation, deleted and corrupt content, empty/bounded pages,
reader admission, content-free failures, unchanged quota/lease/current state, and a
real save committed between list reads under the repeatable-read snapshot. This API
is read-only; an embedded historical preview and its UI acceptance follow in E06.3b.

## Exact historical downloads

`GET /api/documents/{identity}/versions/{version}/download` returns the selected
retained DOCX bytes, never a regenerated file or the latest revision as fallback.
It shares authenticated owner checks, the two-reader admission limit, verified
storage reads and the archive-size bound with preview/current download. Selection
loads only file metadata, not the potentially large working document/review JSON.
The response uses the DOCX MIME type, `Cache-Control: no-store`, `nosniff`, a safe
UTF-8 attachment filename and `X-Fillable-Version` equal to the selected revision.
Current download continues to identify and return the current revision.

This read allocates no file, reservation or version and needs no editing lease.
Missing/deleted/unowned or wrong-document selections return 404; corrupt or oversized
files fail explicitly, busy readers return 409, and dependency errors expose no
content. Administrator role does not grant access to another owner's history.
Reopening tests compare original bytes and edited/review-only file/model pairs with
verified structural correspondence and the immutable-original exporter. Real gateway
browser tests download original and newer revisions separately and reopen the saved
workspace. Historical panel preview/download controls are implemented in E06.3b. These checks
do not claim Microsoft Word validation.

## Restore as a new revision

E06.6 adds `POST /api/documents/{identity}/versions/{version}/restore` with the
current `source_version_id`, tab `client_id`, server `lease_id`, CSRF token and
required `Idempotency-Key`. The selected revision must belong to this active owned
document. The server verifies its saved bytes and matching document/review pair,
then writes a separately charged copy through the shared storage service. The
selected bytes are unchanged and source anchors remain tied to this document's
immutable original; this is not an independent-document rebase.

Save and restore share the same final transaction: recheck active session, current
revision, live lease and quota; insert a new version; advance the current pointer
and the same lease; retire old processing and enqueue new work. Restore additionally
rechecks that the selected file is still retained. Failure leaves the previous
current version intact; quota/disk failure never removes history to make room.

A committed retry returns the exact `saved_version_id` and metadata alongside the
current resource, which may have advanced since that operation. It does not reopen
the selected source or allocate another copy. Clients must compare exact saved and
current identities before adopting a restore result. Unknown outcomes retry the
same key and request; definite aborted operations require a fresh key.

Migration `0010_revision_provenance` adds same-owner, same-document parent and
restored-from references, backfills parents by existing revision number and refuses
a downgrade while provenance exists. All new saves record their previous current
revision. Restores also record the selected revision, exposed in history metadata
as `restored_from_version_id` and `restored_from_number`. Original uploads and initial
independent copies have no parent. Future retention keeps metadata tombstones so
removing an old file cannot erase these references. Use a forward-compatible recovery
image when populated provenance prevents an older schema downgrade; preserve data.

The restore API does not know browser drafts. E06.3b supplies explicit unsaved-work
confirmation and retains the live draft until an exact-current restore acknowledgment.
The E06.6 API verification is separate from the E06.3b history UI acceptance below.

## Workspace history panel

E06.3b adds history inside the workspace for templates and documents. The revision
list shows localized time, readable saved size, current marker and restore origin,
with bounded pages of 20 and explicit refresh/older-page controls. Opening history
keeps the live editor, its undo history and proposed title mounted. A visible message
explains that the unsaved draft is preserved; return to editing resumes that same
state. The separate historical adapter is read-only, exposes that accessibility
state, displays saved fields and has no editing or save callbacks. Preview never
updates the current revision. Language changes preserve both draft and selection.

Historical downloads check the returned revision header before creating a browser
file. A mismatched result is rejected. List/preview/download failures expose explicit
retry paths. A newer current UUID from history prompts reopening rather than rebasing
an unsaved draft silently. All history remains retained; E06.5 will add the visible
operator retention policy before any automatic pruning.

Restoring confirms replacement of an unsaved draft/title. The client first commits
or retries the exact selected request, then loads the exact returned current pair.
Only successful loading replaces the live editor and resets its local undo/draft
state. Quota failures, network errors and failed content loads preserve the original
draft. A committed-but-unloaded result remains retryable with its original key, even
across closing history or switching language. Retry identifies the original selected
revision and reconfirms replacement of any newer local draft. Old replay results
with a newer server current revision never replace the draft. Pending save/restore
operations coordinate mutation, navigation and dirty guards; no historical autosave
is introduced.
