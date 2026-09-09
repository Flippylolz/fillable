# Working field review

E04.5b provides editor transactions for review; E04.5c supplies the localized sidebar.
Production persistence and matching revision metadata remain E06. The current task
must not be described as saving review decisions to the server.

## Attach and map proposals

`attachReview` accepts a source-generated field snapshot only for the expected saved
revision. It resolves the exact part/paragraph/control identities and verifies current
values. Span offsets are Unicode code points from Python; the adapter converts them
to ProseMirror UTF-16 positions, accounting for native-control node tokens, tabs and
locked inline regions. Protected/cross-paragraph ranges and nonempty zero-width
locations are rejected. Existing controls retain their unique identities. Duplicate
identities, changed source values and stale revisions cannot attach a review snapshot.

Working review records live in the editor document's `review` root attribute. This is
editor metadata, not rendered document text or an authoritative server-side snapshot.
Each record retains candidate/occurrence IDs, original reason/source key, context,
label, text type, explicit group key, decision and live location. Missing location is
separate from acceptance/dismissal, so deletion does not erase decision provenance.
The original discovery revision remains recorded; it is separate from future save
revision fences.

Ordinary document transactions map span boundaries and verify the original proposed
text still occupies a supported range. Surrounding edits move anchors; edits that
remove or invalidate the target mark it missing. Equal text elsewhere is never a
substitute. Native/accepted controls are located by immutable unique identity; missing
or duplicated identities are explicit. Selection-only transactions do not alter review
metadata or mark a document dirty.

## Review operations and history

- Accept converts exactly one verified span or empty paragraph into a uniquely identified
  plain-text control. Original text and source formatting are retained. An explicit source
  key or chosen group key can link occurrences; otherwise acceptance creates an independent
  key. Grouping does not choose a winning value or mutate existing values.
- Dismiss changes only review metadata, leaving document content unchanged. It can be undone,
  and the dismissed proposal can later be accepted. Existing accepted controls are removed
  through the editor's control-removal operation, not hidden through a suggestion dismissal.
- Configure changes a proposal's label/group/type or the corresponding live control's
  alias/tag. Labels and keys follow E04.5a bounds (256/512 code points, nonblank, no
  control characters), and reject text DOCX XML cannot store. E11 widens the type
  choice to `text`, `number`, and `date`: accept keeps the proposed kind unless the
  review supplies another, configure rewrites the review record's type in one undoable
  step, and the type never changes DOCX control properties because it is fill-time
  metadata, not a control attribute. Invalid operations preserve the current document
  and metadata.
- Focus selects the precise proposal/control range without changing the document. Missing
  locations cannot be focused or accepted.

ProseMirror's built-in document-attribute step keeps review metadata in the same history
transaction as content changes. The dispatch path appends mapped review state after linked
value and paragraph-identity processing. Undo/redo already restores the inverse metadata
step, so it must not be mapped a second time. Value propagation also skips history
transactions: undo restores the exact previous values, including conflicts where one
occurrence already matched the latest shared value. Locale changes preserve the mounted
editor, document, metadata and history and do not trigger a document change callback.

## Workspace sidebar and result loading

The owned workspace loads the result for its opened source revision. Pending results
poll every two seconds, stopping after 60 reads with a manual status retry. Failed or
legacy inspections can be explicitly restarted with CSRF protection. Navigation aborts
obsolete requests; late results never attach to another revision. Initial attachment
does not create unsaved changes. If editing already changed the document, attachment
is rejected and reopening the saved document requires confirming discard of the draft.

The collapsible review panel separates proposed, accepted and dismissed records, with
localized counts and ten records per page. Each record shows its reason, source context,
label, localized type choice (text/number/date) and explicit value group. Group choices
use readable labels rather than internal identifiers. Users can focus, configure, accept
and dismiss valid proposals;
missing locations remain visible with unavailable actions disabled. Applying a group
preserves conflicting existing values until a subsequent value edit.

Sidebar value cards render the record's type: text keeps the multiline textarea,
number uses a decimal input that preserves the user's exact text (comma decimals and
space thousands included), and date uses a picker that reads any supported day-first
or ISO form and writes the canonical `ДД.ММ.РРРР` document format while leaving
separators of directly edited values untouched. Empty values stay valid for every
type; a nonempty number that does not parse and a nonempty unparsable date raise the
same recoverable field-value issues as other invalid drafts, remain in the draft, and
block saving through `fieldValuesValid`. The server keeps treating values as bounded
text: value-format checking is a workspace contract, not a new rejection path for
saves.

The panel shares editor history and preserves unapplied label/group inputs across a
profile language change. Ukrainian and English controls, errors and pagination use the
same catalogs as the rest of the application. The bounded scrolling sidebar retains the
Google Docs-style workspace layout on desktop and mobile. These remain open-draft
operations: saved download bytes, server discovery results and storage usage are unchanged.

## Verification and boundaries

The source-derived `frontend/prototype/fields.json` is generated by the actual Python
detector beside its document model. Required CI regenerates both and rejects drift.
Tests attach all 28 corpus proposals and verify exact selections, including the empty
cell. Additional tests cover astral Unicode, native node tokens, split text, protected
regions, repeated text, acceptance/dismissal/configuration, surrounding edits, deletion,
invalid source/metadata, duplicate identities and exact undo/redo. A mounted-editor test
checks missing-control metadata and history across a Ukrainian/English switch.

Future save integration must validate and serialize the working review state against the
current document and source revision. Accepted inferred proposals now refer to live controls;
the server schema must explicitly support that origin/location combination and missing
records rather than silently relabeling them as native controls or retaining invalid spans.
Copied saved revisions must carry independently rebased metadata. No claim of those E06
behaviors is made by this transaction subtask.

## Manual controls and missing locations

E05.4 records each manually created control as an accepted manual location, preserving
its immutable identity, selected source runs and independent group key. Creating a field
and its record is one undoable operation. Moving a uniquely identified control updates
its location without creating another record. Removing it unwraps the text and retains
an explicitly missing record; undo restores the same identity and enables navigation.
Duplicate identities are ambiguous and cannot be focused or removed arbitrarily.

When editing begins before discovery attaches, existing controls receive local native
records and new controls receive manual records. This draft has `sourceVersion: null`: it
is explicitly unbound, not a fabricated saved discovery result. A later result cannot
overwrite it; reopening the saved revision uses the existing discard confirmation.
Ordinary edits in documents without controls do not invent review metadata. E06 must
validate and bind persisted metadata against the actual saved revision.

Manual labels are trimmed and bounded to 256 Unicode code points, excluding control and
invalid XML characters. Creation requires nonempty editable text in one paragraph,
outside existing fields or protected content. At 2,000 live controls or review records,
creation reports the document limit. Invalid requests preserve selection and source text
and display a localized error. Manual records use the existing accepted filter and
missing-location feedback; they are not separate server-side writes.

E05.5 defers review root-attribute changes during native composition to avoid redrawing
its active DOM. On commit it maps the accumulated composition steps once, alongside linked
value propagation and any strictly mapped control restoration. The same native history
identity keeps content and metadata undoable together. Pending composition is exposed to
future save integration; an intermediate candidate must not be persisted as a completed edit.
