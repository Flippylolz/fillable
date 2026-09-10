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
changes preserve the draft and its validation state. Since E11 the entry control follows
the record's reviewable type (text textarea, decimal number input preserving exact user
text, and a datepicker writing canonical `ДД.ММ.РРРР`); unparsable nonempty number/date
values raise the same recoverable issues and save block under
[Working field review](FIELD_REVIEW.md).

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
drafts and never reports document edits as saved. E06.2d/E06.3b deliver the save and
history toolbar integration required by E05.6b.

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

## Atomic saved revisions (E06.2c)

`POST /api/documents/{identity}/versions` accepts a typed JSON working document,
expected source revision, tab/client identity and lease generation, with exact-origin
CSRF and an idempotency key. A save is admitted through the shared two-request upload
bound, reads at most 64 MiB of JSON within 30 seconds, and retains the existing model,
OOXML and 10 MiB output bounds. Only this save route has the matching 64 MiB gateway
limit; other API routes keep 24 MiB. Parsing/export remains in the Python thread pool.

A new operation checks the active owner, current revision and live session/tab/lease,
validates working review against the current or trusted persisted origin, and exports
against the verified immutable original. Storage reserves and charges each retained
revision file, including a review-only revision with identical DOCX bytes. Finalization
rechecks owner, revision and lease using database time, commits DOCX/model/review as
one version, advances current and the same editing lease to that version, retires old
pending processing and records the new processing intent. Failures leave the previous
saved version intact; uncertain commit responses are resolved by the same operation key.

The response distinguishes `saved_version_id`, number/time/bytes/digest from current
`resource`. A committed retry returns its exact saved revision even if another save
has since advanced current, without reopening or exporting a new source. Deleted
results are not recreated. Every retry still requires an active authenticated owner.
The next UI task must acknowledge the exact local snapshot it sent, retain later
edits, distinguish a stale replay from current, and keep one tab identity across a
successful revision transition. Old-source lease release cannot remove the updated
lease. No manual-save button or autosave is claimed by this backend task.

Migration `0009_saved_review` stores nullable `document_versions.field_review` beside
the matching model; existing embedded review is moved without loss and stripped from
the model. Owned content reads combine the pair, copies rebase and split it, and
permanent deletion clears both. A populated-review downgrade is refused. Older app
images that only read embedded review are not compatible after this migration; keep
the migrated data and use a compatible forward application release.

Processing verifies saved bytes against the exact stored source-anchored model and
runs detection against that model. It does not replace its identities with positions
from reparsing the exported XML. Discovery remains proposals, separate from retained
working review; accepted origins and missing/dismissed records survive reopen/copy.

When native/manual review still has a local null origin, a save binds its persisted
copy to the trusted prior origin or first save's expected source revision. Subsequent
null-origin snapshots from the same mounted editor retain that binding. The request
and undo history are not mutated; reopening loads a bound review and does not enter
a repeating stale-discovery/reopen prompt. This changes provenance only, not DOCX
bytes, locations, labels, values or user decisions.

## Manual saves (E06.2d)

The workspace toolbar saves a detached snapshot from the mounted editor. New saves
require valid field values, settled native composition and a synchronously valid
editing lease. One cryptographic client identity survives the tab's own saved-version
transitions; cleanup for the old source cannot release the advanced generation.

Acknowledgment records the exact local revision sent. It updates saved resource
metadata and download identity without replacing the editor document, selection or
undo history. Edits made during the request stay unsaved; undo after acknowledgment
also changes the local revision. A proposed title is tracked separately, so saving
document content never clears it. Rename/reload requests are serialized with pending
document saves; zoom, highlighting and document editing remain local. Normal route
and authentication guards protect active requests. Locale/profile navigation after
a request retains the same mounted editor and draft.

Network errors, timeouts, 5xx and in-progress results retain the original detached
body and idempotency key. Retry sends that attempt even if newer input is invalid or
editing has paused; it never captures a new draft under an old key. Definite failures
leave the draft and permit a new operation where editing access allows it. A replay
whose saved version differs from the server's current version does not adopt that
newer UUID as the old draft's base. Revision/lease/authentication failures pause access.
The user must explicitly reopen after a conflict; unknown save results receive an
additional discard explanation. Reopen and unmount abort/ignore obsolete responses.

Confirmed reviewed snapshots allow later proposals to recognize the retained local
review without rewriting its null origin inside undo history. This acknowledgment
is outside the document; actual reopened review uses the server's persisted origin.
Proposals never replace user review. The UI provides Ukrainian/English save, pending,
retry, failure and exact-acknowledgment states. This task adds manual save; automatic
save remains E06.7; the history panel is delivered in E06.3b.


## History panel and draft-safe restore (E06.3b)

The toolbar opens saved history inside the workspace. A separate read-only adapter
previews exact persisted revisions while the original draft/editor and proposed
title stay mounted. Return to editing keeps the same undo stack and local state.
Localized dates, readable byte sizes, current markers, restore provenance and bounded
paging use the saved history APIs. Exact historical downloads verify the response's
selected revision header before producing a browser download.

Restore confirms replacement of unsaved content/title and coordinates with pending
manual saves and editing access. It adopts a new editor instance only after the exact
restored current pair is loaded. Unknown or failed loads retain the original draft
and request across history/profile/language changes; retries cannot switch to another
selected revision. Explicit reopen offers a separate discard decision. The full
contract and retention boundary are in [Saved history](HISTORY.md). Autosave remains
E06.7 and must not save a historical preview.


## Autosave (E06.7)

A newly opened workspace enables document autosave. After two seconds without a new
editor revision, the workspace uses the same immutable snapshot, quota, editing-lease
and idempotency protocol as manual Save. Polling, selection and initial detector
attachment do not create revisions or restart the timer. Title changes remain an
explicit separate operation. The workspace settings checkbox can disable future
autosaves; its value survives profile/language changes and explicit reopen/restore
within the same mounted workspace, but is not an account preference.

Autosave pauses for a historical panel, unavailable editing authority, native
composition, invalid field values, active mutations (including profile/library operations), uncertain operations or a save
error. The timer also rechecks the synchronous editor snapshot and live credentials
before submitting. Historical preview has no save callback; returning to editing
resumes the same draft and schedules eligible live changes. Turning the setting off
does not cancel an already submitted operation or discard its unknown outcome.

Saving/saved status acknowledges only the submitted editor revision. Newer typing
stays dirty through a delayed acknowledgment and receives a separate later save
against the newly acquired current-version lease. A failure keeps the draft and
pauses automatic retries, including after later edits. The explicit Save/Retry action
resolves the problem; uncertain retries keep their original key/body, then a newer
draft can autosave separately. Stale current conflicts continue to require explicit
reopen/discard handling. Retained autosaves count toward the displayed storage policy
and allowance; no failed save invokes retention to make room.

Browser acceptance covers default-on debounce, no writes for detector attachment or
title edits, the real settings toggle and locale preservation, native composition,
historical pause/return, lost committed responses and exact retry, quota failure,
manual recovery and reopening the saved pair. Manual editing/review regression flows
explicitly disable autosave through settings when asserting an intentionally unsaved
draft. Hook/component tests cover cancellation, polling renders, delayed acknowledgment
and the save-error pause. See the epic record for measured validation.

Session recovery retains the mounted draft, undo history, settings and pending save
snapshot while the page is hidden and paused. Same-account sign-in updates CSRF and
reacquires editing authority; a still-live lease may require an explicit retry after
expiry. Switching accounts uses the unsaved-work discard guard and remounts account
pages. Obsolete write responses remain uncertain and use the existing exact retry
protocol. See [Authentication](AUTHENTICATION.md).

### Source presentation (E09.1)

Current and historical content include a separate optional `presentation` object.
The source reader uses the owner's retained original, whose identities anchor saved
models, so existing documents and historical selections share their proper source
formatting. Presentation is never copied into the live JSON model, undo stack,
review state or save payload. Scoped CSS is isolated per editor/history instance;
source graphics use safe read-only node views. Page width is retained at mobile
sizes with canvas scrolling rather than reflowing the document to phone width.

### Boxed date entry (E09.2)

The workspace date action accepts one calendar date and distributes DDMMYY or
DDMMYYYY into the current selection. Supported targets are six/eight individual
positions separated by vertical bars, six/eight table cells, or three populated
cells containing day/month/year groups of 2/2/2 or 2/2/4 digits. Selection supplies
source positions; it is never inferred from screen coordinates. Separators, cell
structure, paragraph identities and existing source marks are retained. All digits
change in one undoable transaction using the ordinary revision/quota/history path.
Invalid dates, ambiguous selections, protected objects and unavailable edit leases
produce localized errors without mutation. This is an explicit fill action, not
automatic date inference or an editable conversion of arbitrary drawing objects.

Borders now include internal horizontal/vertical table edges and inherited table
styles, with direct cell overrides; paragraph/run outlines and DrawingML line
weights retain bounded source values. Source files that only contain separator
characters do not acquire new graphical boxes or altered originals implicitly.

### Checkbox controls and toggling (E09.13)

Native Word checkbox content controls (`w14:checkbox`) are no longer generic
unsupported content: import maps each control to a bounded checkbox node carrying
its checked state, rendered as an accessible ☐/☒ mark that toggles by direct click
or Space on the selection and participates in undo/redo like any document change.
Export updates only that control's `w14:checked` value and its state glyph;
unchecked documents save byte-identically, and malformed controls stay protected
as before. The glyph action mirrors the boxed-date pattern: selecting exactly one
unambiguous ballot-box character (U+2610/U+2612) and toggling swaps the pair in
one undoable transaction while preserving run formatting; symbol-font private-use
codes (Wingdings and similar) are deliberately not paired because the run font is
not part of the editing model and a wrong swap could corrupt ordinary text.
Inline DrawingML rectangles and VML rectangles — the way many converted forms draw
checkboxes — are extracted as bounded, read-only shapes rendered in the text flow
at their anchor position, matching Word's inline rendering; anchored shapes keep
their source offsets relative to the paragraph box. Their geometry is presentation
only and never becomes editable text or a filled value. An `AlternateContent` run
carries its DrawingML choice and VML fallback as one drawing, so each rectangle
renders once. Rectangles with an explicit fill color additionally toggle like
checkboxes: clicking swaps the fill between the form's own dark color and a
cleared white box, stored as a bounded per-run override (`shapes`) on the locked
run in the editor model; export rewrites only that rectangle's fill value in the
DrawingML choice and its duplicate VML fallback, an unchanged or empty-override
document stays byte-identical, and shapes with implicit fills (no color, `noFill`)
together with run identity remain immutable. Checkbox-sized anchored rectangles
are re-anchored after layout onto the rendered text line nearest their Word
offset, so they stay level with their labels when the editor wraps a line
differently; larger drawings keep the exact anchored offset.

### Visual page breaks (E09.15)

The mounted workspace and historical preview show approximate page boundaries so a
reader can see where one page ends and the next begins. The adapter measures top-level
blocks against the source page geometry already delivered for layout (page height and
margins from `sectPr`) and renders a dashed marker with a localized "Сторінка N"/"Page N"
label between the blocks that begin a new page. Markers are ProseMirror widget
decorations only: never part of the document model, undo stack, review state, save
payload or exports, hidden from assistive technology, and numbered in reading order.
Measurement reruns after edits, zoom changes and layout/resize/font changes; marker
positions honor the zoom scale and exclude previously rendered markers.

Breaks fall on block boundaries and cannot split a paragraph or table row, so the
marker shows the last block boundary before Word's exact break position. Documents
whose presentation lacks page geometry (and header/footer sections) show no markers.
This is deliberate flow approximation, not Word pagination; exact break positions,
floating-object interactions and print layout remain outside the proven support matrix.
