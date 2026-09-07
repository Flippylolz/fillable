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

## Native input and history

E05.5 makes identical sidebar updates idempotent: they do not dispatch, advance the local
revision, or add undo entries. Native Enter/Shift-Enter inside one field insert line breaks;
arrow keys collapse a selected field in editor state before subsequent deletion. Ordinary
caret navigation and input outside fields retain ProseMirror's behavior.

Active IME composition belongs to the native editor. Linked occurrences and root review
metadata update after composition settles, because rewriting them during candidate input
can redraw the DOM and interrupt the native range. The adapter retains all composition
steps for exact review mapping and preserves the native composition history identity.
A fast commit that unwraps the selected control can restore only its mapped, editable text
range with the original immutable control identity. Protected or incompatible ranges are
not substituted. This does not use matching text elsewhere in the document.

Snapshots/presentation expose `composing`; consumers must wait for it to clear before saving
or exporting. The opt-in proof disables export while composition is pending. The pinned
ProseMirror view flushes queued composition mutations after 20 ms; the adapter commits
linked/review changes afterward and cancels its pending callback on destruction. Browser
verification uses Chromium's native IME protocol, including cancellation and an unchanged
final candidate. This is not a claim of testing every physical keyboard/OS input method.

## Workspace settings and display titles

E05.6a adds a back-to-library action and a collapsible settings panel inside the workspace.
Zoom (50–200%) and field highlighting are view preferences; they do not alter the working
model, source formatting, review metadata or saved bytes. Settings and the mounted editor
survive profile/language/back navigation. The sidebar keeps its normal size while the
canvas scrolls within the available width. Unsupported content retains its warning color.

`PATCH /api/documents/{identity}/title` requires the current owner session and CSRF token.
It checks the opened revision and expected previous title under a resource lock, then
updates only the title/timestamp. An already completed identical rename returns the same
result without another update. Competing names cannot overwrite each other silently.
Title validation retains the existing 160-code-point metadata bound and rejects invalid
Unicode. Original filename, immutable originals, working/saved models, field results,
revision identity and quota accounting remain unchanged, including for an over-quota owner.

The proposed title stays in the form through failures and language changes. A title-only
conflict can reload current metadata while retaining the proposed name; a changed saved
revision uses the existing explicit reopen/discard flow. Pending title edits participate in
leave guards. A successful rename refreshes library metadata without losing upload/editor
drafts and never reports document edits as saved. Save/history toolbar integration remains
E05.6b after the corresponding E06 operations are implemented.

## E06.1a editing lease API

`POST /api/documents/{identity}/editing-lease` accepts an `acquire`, `renew` or
`release` action with the expected source version and a random per-editor `client_id`.
Renew/release also require the server-issued `lease_id`; acquisition forbids it.
The authenticated session, client ID and generation must all match. Another live
holder receives `operation_conflict` with `reason=lease_busy`; failed renewal uses
`lease_lost`, and an outdated source uses `revision`. Responses contain no holder
or session identity, use no-store, and require current authentication and CSRF.

Resource-row locking serializes acquisition after the account/session check. Leases
last 60 seconds according to PostgreSQL time. A same-holder live acquisition safely
retries/renews; expiry or authentication revocation permits a new generation.
Expired renewals cannot resurrect a lease. Release is idempotent and its old generation
cannot remove a successor, even if the same tab reacquires. Session expiry, idle
expiry and revocation invalidate ownership. Deleted or unavailable resources cannot
be acquired; deletion removes the lease in the same tombstone transaction.

Migration 0008 creates one bounded row per resource with owner/version foreign keys,
without changing original files, retained revisions, models or quota. Downgrade
refuses populated lease state. Lease generations are coordination metadata, not
standalone authentication credentials. Future saves must check this fence in their
commit transaction; this API alone does not implement persistence. E06.1b adds the
workspace acquisition/expiry and retained-draft flow; E06.2 adds fenced saves. Clients
must conservatively subtract request elapsed time from the returned validity period
and never persist an editor snapshot while composition is pending.

## E06.1b mounted workspace access

The workspace acquires a lease before enabling document edits, renews every 20
seconds, and checks its conservative monotonic deadline at each mutation boundary.
A suspended timer cannot authorize the next edit. Requests time out after 10 seconds;
conflicts, network/authentication failures and local expiry pause editing and retain
the mounted draft. Retry explicitly reacquires against the same saved source; a newer
revision offers the existing discard-confirmed reopen flow. No forced takeover or
save is implied. Title settings retain their independent metadata conflict checks.

Typing, field changes, review mutations and undo/redo are guarded in the adapter,
as well as disabled in the UI. Selection/copy, field navigation and review browsing
remain available. Existing IME composition may settle its already-started draft and
linked fields after access is lost, then the document becomes read-only; a new
composition cannot start. A future save must require both valid access and a settled
snapshot. Reacquisition retains the document instance, review state and undo history.

The initial effect defers acquisition one event-loop turn so React StrictMode cleanup
cancels its test mount before sending a request. Resource changes/unmount cancel
pending work and release only a known server generation; page exit makes a best-effort
keepalive release. Expiry is the fallback for an unknown committed/lost response.
Late results after unmount cannot enable editing. Mounted library/profile navigation
and language changes preserve the holder and draft; paused-state messages are localized.

## E06.2a persisted working-review contract

`fields.working.validate_working` returns a detached document/review pair for a
future save transaction. The document has its root review attribute removed; the
review preserves the editor's exact accepted, proposed, dismissed and missing records.
It is a separate contract from asynchronous discovery `FieldSnapshot`: an accepted
inferred suggestion now points to a control while retaining its inferred reason, and
a missing record can retain obsolete coordinates without being remapped to equal text.
No file write, revision or database migration is performed by this validation step.

Source binding accepts the current source revision or a trusted previously persisted
origin, supplied by the caller. Null origins allow only locally tracked native/manual
records. IDs and occurrence IDs are unique; every live control is tracked once, with
matching label/key and presence. Accepted items use control locations; proposed or
dismissed items use spans. Nonmissing spans must match exact current paragraph text,
use valid UTF-16 boundaries, avoid protected/control content and not overlap. Empty
ranges are valid only in genuinely empty paragraphs. Missing spans stay missing even
if their old text later appears at the same coordinates. Reappearing controls require
matching live presence, never a false missing marker.

Traversal bounds include metadata UTF-8 bytes, nesting, model nodes and record count.
The index accounts for ProseMirror container tokens and astral UTF-16 widths; indexed
paragraph/segment lookup avoids repeatedly scanning the entire document for each field.
Unchanged legacy labels/keys, including an empty native alias, are preserved under the
total budget. OOXML validation and changed-property creation limits remain mandatory
through `DocxExport` against the immutable original; this contract does not replace
source validation, owner/lease checks, quota reservation or the later atomic save.

The shared synthetic working fixture is generated by real editor transactions and
compared in normal frontend CI. Backend tests validate that same artifact, detach the
pair, export against the retained original and reopen its Ukrainian/multiline fields.
See [Test corpus](TEST_CORPUS.md) for the artifact and generation procedure.

Native discovery may use the grouping key as a display label when the OOXML alias
is empty. Attaching working review takes the actual control label/key from the editor,
so that fallback is never mistaken for an applied alias change during persistence.
