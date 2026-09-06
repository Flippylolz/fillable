# Persisted workspace entry

E03.4c adds `/editor/:id` within the four-page contract. The library opens either a
template or an individual document in the shared E00 editor. The compact toolbar,
paper canvas and sidebar follow the user-requested Google Docs-like visual direction;
the editor remains structural rather than a Word pagination engine. See
[Editor feasibility](EDITOR_FEASIBILITY.md) for the verified support matrix.

`GET /api/documents/{identity}/content` requires an authenticated owner and an active
resource. One query resolves the current revision, stored model and file identity
together. The storage reader verifies the selected file's ready state, size and
digest before returning that same revision's model and resource metadata. File-read
admission is shared with downloads. Responses and errors are no-store; no physical
path or unauthenticated prototype route is exposed. The endpoint performs no retained
write or new allocation. Deleted and foreign resources cannot be opened.

The workspace reuses `DocumentEditor`, including direct supported text edits, linked
existing-control values, manual fields, selection, undo/redo and protected unsupported
regions. Initial state says a saved revision was opened; a document transaction marks
local work unsaved. Downloads remain explicitly the latest saved DOCX. This task does
not persist new edits: leases/revision-checked saves, history and autosave remain E06,
while E04/E05 complete discovery/review and workspace controls. No false save response
or fake persistence is provided by this entry point.

One workspace stays mounted while visiting the library/profile, preserving the editor
view, draft, selection and undo history through language changes. Opening another
resource with a dirty workspace requires discard confirmation. Back/forward applies
the same guard. Signing out with either an upload or editor draft also requires
confirmation; the browser leave warning covers refresh/close. Opening the same resource
restores the existing mounted draft. An authenticated direct reload of an editor URL
loads its saved revision. Error/retry/loading states do not fabricate editable content.

Unit checks exercise verified model loading, ownership/storage failures, direct URL
entry, editor identity across language/navigation changes, history and logout guards,
error retries and aborted requests. Production browser checks edit an existing control,
change the account language without losing either an upload or editor draft, undo/redo,
open another resource with cancel/confirm, and retain exact saved-download bytes.
