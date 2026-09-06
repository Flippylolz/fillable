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

## Editor adapter

E05.1 isolates ProseMirror lifecycle and transactions in `frontend/src/editor/adapter.ts`.
`mountEditor` loads the verified source model once and exposes only the operations used
by the workspace: field enumeration through presentation updates, create/update/focus/
remove, review actions, undo/redo, discovery attachment, accessible labeling, snapshot
export and destruction. React controls receive field identities and values without
depending on ProseMirror positions, views or transactions. Both resource kinds use it.

The adapter owns its input and returns detached document/review snapshots. Mutating an
export, callback payload or presentation cannot modify the live editor or its source
anchor baseline. `exportSnapshot` includes a local monotonic change counter: authored
document transactions, including undo/redo, advance it; selection, initial discovery
attachment and interface-language changes do not. This counter is not a server revision
or editing lease. E06 provides the authoritative save/version fence.

The existing development round-trip proof exports these same model snapshots through
the Python source-preserving DOCX adapter, then reopens its returned model. Production
loads use the owned content endpoint and downloads remain explicitly saved bytes until
E06. The frontend adapter does not write DOCX files, bypass quota accounting or rebuild
documents from rendered HTML. Locale changes update the existing editor's accessible
label while retaining document state, selection, review inputs and history.

## Sidebar navigation and review feedback

E05.2 gives each field occurrence an individually named card, including its localized
position to distinguish repeated labels. Previous/next navigation uses immutable control
identities and selects the precise editor location without a document transaction. With
no selected field, next starts at the first and previous at the last; boundaries disable
the corresponding button. The selected card has a visible marker and `aria-current`,
and a status message reports its position. Language changes preserve that selection.

Linked occurrences remain separate when their values conflict, with an explicit review
message; navigation never resolves a conflict or chooses a value. An empty sidebar explains
manual selection and proposal review. Label/group validation continues in the adjacent
review panel, whose invalid inputs now reference their localized error description.
Acceptance/dismissal/missing states and undo remain the same editor-owned review metadata.
Long/multiline values are covered below. Manual creation and moved/missing control
records follow [Working field review](FIELD_REVIEW.md); invalid creation retains the label
and selection with a specific associated error. Undo restores removed control identities.

## Field values and recoverable validation

E05.3 uses resizable multiline textareas for sidebar values. Newlines, tabs, long text,
Ukrainian characters and supplementary Unicode use the same editor transactions as
ordinary text. Direct editor changes refresh these controls; there is no independent
sidebar value store. Linked changes and their undo/redo retain the existing identities
and source formatting. The Python exporter already emits line breaks/tabs with multiline
control properties; the browser now exercises that path through actual export/reopen.
Native multiline insertion can replace a control's DOM wrapper before ProseMirror parses
the mutation. A scoped `beforeinput` handler applies multiline text while the selection
still refers to that control; a plain-text paste handler follows the same path. Input outside a single field and `beforeinput` during active composition remain with
the ordinary editor handlers.

Field values follow the versioned metadata limit of 65,536 Unicode code points and XML
1.0 text validity. Empty text, tab, LF, CR and valid supplementary characters are allowed;
forbidden XML characters and lone surrogates are flagged. Invalid input remains in the
working document and linked sidebar controls with a localized, associated error. Users
can correct or undo it; no truncation, replacement or silent discard occurs. Language
changes preserve the draft and its validation state.

Adapter snapshots and presentation expose `fieldValuesValid`. This only describes field
values, not full DOCX/model validity or server authorization. The opt-in round-trip proof
disables export until invalid values are corrected. E06 must consume this state for save
UX and independently validate every server-side save; current production saved-download
bytes and storage usage remain unchanged by draft editing.
