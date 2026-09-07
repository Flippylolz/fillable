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
workspace. Historical panel preview/download controls follow in E06.3b. These checks
do not claim Microsoft Word validation.
