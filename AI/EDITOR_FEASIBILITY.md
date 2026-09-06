# Free editor feasibility

Status: E00.1–E00.4 verified and merged. E00.5 adopts the project-owned ProseMirror/Python source-package implementation, with the explicit support matrix below. Production feature integration remains E03–E07.

## Selection boundary

The full path must work without required fees in both development and production: DOCX import, direct editing, field creation/focus, two-way sidebar updates, undo/redo, and DOCX export. A free trial or a free viewer with a paid editing/export API does not qualify. Hosting stays local, backend application logic stays Python, and AI is outside MVP.

D021 also requires Ukrainian and English UI. Verify localization hooks for every exposed editor toolbar, menu, dialog, tooltip, and accessible label, including whether missing Ukrainian strings can be supplied through the free integration or project-owned controls. Record any gap in the support matrix; an English-only embedded UI does not satisfy the [Localization contract](I18N.md). UI locale changes must preserve the current document and editor state.

## Research inputs

| Option | Evidence and implication |
| --- | --- |
| A complete free DOCX editor | Evaluate the exact edition, dependency licenses, APIs, and server requirements. No such integration has yet passed our workflow. Do not assume a community edition exposes its commercial edition's APIs. |
| ProseMirror with a project-owned DOCX adapter | ProseMirror supplies an extensible editor model and transactions; its core packages use MIT licensing. It is a building block, not a ready-made Word round-trip engine. We would own import/export mapping, field nodes, and supported formatting. |
| docx-preview | Its Apache-2.0 project renders DOCX to HTML. It can support preview experiments but is not a complete editable DOCX round-trip solution. Rendered HTML must not become the canonical export source. |
| Tiptap DOCX Conversion | The documented conversion package is subscription-based. It does not qualify for the free-only MVP; do not confuse editor-core licensing with conversion licensing. |
| SuperDoc / ONLYOFFICE | SuperDoc documents an AGPL editor and a separately proprietary DOCX engine. ONLYOFFICE's external Automation API is part of an extended Developer license. The previous paid integration proposal is superseded; any alternative free route needs separate verification. |

Sources: [ProseMirror overview](https://prosemirror.net/), [ProseMirror license](https://github.com/ProseMirror/prosemirror-state/blob/master/LICENSE), [docx-preview project](https://github.com/VolodymyrBaydalka/docxjs), [Tiptap conversion](https://tiptap.dev/docs/conversion/getting-started/overview), [SuperDoc engine terms](https://docs.superdoc.dev/resources/docx-engine-license/), [ONLYOFFICE Automation API](https://www.onlyoffice.com/automation-api).

These are component facts, not proof that any combination satisfies Fillable. Verify maintained upstream locations, exact releases, dependencies, and notices during E00 before pinning them.

## Custom implementation proof

If a complete free option fails evaluation, prototype a scoped editor using open components and the DOCX format specification. The following is a proposed approach, not a claim of implemented fidelity:

1. Preserve the original DOCX package and map supported paragraphs, runs, tables, and field occurrences to stable editor identities. Retain unedited package parts and relationships.
2. Support direct surrounding-text edits as well as sidebar updates through the same transaction model. Mark unsupported content explicitly; do not silently drop it or represent the whole document as an editable HTML conversion.
3. Export supported edits into the package, retaining untouched styles, numbering, media, headers/footers, and relationships. If an edit would invalidate an unsupported structure, reject it with a clear explanation.
4. Verify no-edit round trips, supported edits, repeated fields, field deletion, undo/redo, long values, Unicode, save, and independent DOCX reopening. Distinguish preserved file structure from visual layout compatibility.
5. Record a support matrix with measured evidence. If the proof requires narrowing a user-required feature, present that concrete limitation before treating E00 as complete.

Preserving arbitrary Word layout is the largest engineering uncertainty. A custom editor is an allowed fallback, not an inexpensive substitute we can promise before this proof. Synthetic fixtures can start E00; representative sanitized user documents are still useful for acceptance.

Reference: [Office Open XML document structure](https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document).

## E00.2 comparison and prototype direction (2026-09-06)

This is a source/API/license comparison, not a runtime compatibility result. No
candidate editor engine was installed or executed for this task. Official version
metadata and source locations below were inspected on this date; E00.3 must lock
its actual package versions and retain their notices before running the prototype.

| Candidate / inspected version | Free path and license obligations | Fields, editing and DOCX path | Python/local deployment and UI | Result for this prototype |
| --- | --- | --- | --- | --- |
| ProseMirror state 1.4.4, view 1.41.7, model 1.25.4 (official repository package metadata) | MIT core: retain copyright and permission notices; no subscription or required server. Audit transitive package notices when locking. | Schema nodes/attributes, selection, transaction dispatch and history support a project-owned field model. No built-in DOCX importer/exporter; Fillable must preserve/map the package. | Browser bundle only; existing Python API owns OOXML validation and export. Project-owned toolbar/sidebar strings use existing uk/en catalogs, with no vendor dialogs to translate. Locale changes can update view attributes without replacing editor state. | Preferred E00.3 prototype. MIT components fit the existing stack and undecided project license; fidelity remains the critical unproven work. |
| ONLYOFFICE Docs Community 9.4.0; external Automation API docs | Community code is AGPLv3 with additional notice/attribution terms and separately licensed non-code material. Preserve required UI/legal notices and satisfy applicable source obligations. External Automation API requires extended Developer licensing; its trial is not the free path. | Connector documents content-control events/methods. A Community plugin could use plugin APIs, but that is a separate integration and has not proven stable sidebar synchronization/export in our corpus. | Python can implement callbacks; Document Server adds its own server/conversion stack, including Node server components, beyond the accepted frontend-only Node boundary. Official editor locale directory contains uk/en JSON. Changing language without losing editor history is unproven. | External connector route does not qualify. Do not claim all Community editing is paid. Plugin/server integration and owner-level license implications remain unresolved; not adopted. |
| SuperDoc v2 docs, DOCX Engine terms version 2026-07-14 | AGPL editor and proprietary engine are separate. Terms allow specified dependency uses without a separate agreement subject to restrictions; that does not establish an unrestricted permissive DOCX path. | No engine or derived behavior was inspected, installed or benchmarked. Its public license distinguishes ordinary powered integrations from prohibited substitute-engine uses. | Self-hosting is documented, but exact edition/dependency and uk/en coverage for our integration are unverified. | Not adopted. Do not state the engine is invariably paid. Avoid making Fillable's custom adapter depend on engine materials or behavior; use OOXML specifications and our own synthetic package. |
| Collabora CODE, current official CODE/FAQ and source mirror | CODE is offered free; source COPYING is MPL-2.0, with additional bundled-component notices requiring audit. Upstream's production caution is a support/stability recommendation, not proof of a license prohibition. | WOPI bridge exposes save and UNO commands. Inspected bridge does not establish a complete stable occurrence-ID/read/change/focus contract for the sidebar. Native document editing/export is available, but corpus synchronization remains unproven. | Separate native office server, WebSocket/proxy routing and Python WOPI host needed; retains the Python application backend. Ukrainian UI/core/help PO catalogs exist. In-place locale/history preservation is unproven. | Reserve candidate if custom fidelity fails. No server image adopted or purportedly tested; GitHub's latest release result was mobile, so it is not mislabeled as a pinned server release. |
| Tiptap DOCX Conversion docs | Subscription conversion path does not qualify. MIT editor-core licensing does not cover that service/package offering. | Provides conversion separately from the free core; free core still needs a custom package adapter. | Adds conversion service/dependency requirements; no localization or corpus proof performed. | Exclude the documented subscription conversion path. Direct ProseMirror avoids an extra wrapper for the proposed custom work. |
| docx-preview 0.4.0 (official repository metadata) | Apache-2.0; retain license/notices, audit JSZip dependency if used. | DOCX-to-HTML rendering, without the required editable transaction/export path. HTML cannot become canonical DOCX. | Browser preview compatible with Python; application controls can be localized. | Optional preview building block only, not an editor choice. Not installed. |

Evidence links:

- ProseMirror [transaction/model guide](https://prosemirror.net/docs/guide/),
  [selection/view API](https://prosemirror.net/docs//ref/),
  [state metadata](https://github.com/ProseMirror/prosemirror-state/blob/master/package.json),
  [view metadata](https://github.com/ProseMirror/prosemirror-view/blob/master/package.json),
  [model metadata](https://github.com/ProseMirror/prosemirror-model/blob/master/package.json),
  and [MIT license](https://github.com/ProseMirror/prosemirror-state/blob/master/LICENSE).
  Package metadata names `code.haverbeke.berlin` as the source repository; GitHub
  metadata was inspected as the available official mirror.
- ONLYOFFICE [9.4.0 release](https://github.com/ONLYOFFICE/DocumentServer/releases/tag/v9.4.0),
  [license and additional terms](https://github.com/ONLYOFFICE/DocumentServer/blob/master/LICENSE),
  [Automation licensing](https://www.onlyoffice.com/automation-api),
  [connector events/methods](https://api.onlyoffice.com/docs/docs-api/usage-api/automation-api/connector-class/),
  [server sources](https://github.com/ONLYOFFICE/server), and
  [editor locales](https://github.com/ONLYOFFICE/web-apps/tree/master/apps/documenteditor/main/locale).
- SuperDoc [public engine terms](https://docs.superdoc.dev/resources/docx-engine-license/).
  These are licensing evidence only and are not a design specification for the
  project-owned adapter.
- Collabora [CODE](https://www.collaboraonline.com/code/),
  [FAQ](https://www.collaboraonline.com/faqs/),
  [current source location](https://github.com/CollaboraOnline/online),
  [license](https://github.com/CollaboraOnline/online.mirror/blob/main/COPYING),
  [WOPI message bridge](https://github.com/CollaboraOnline/online.mirror/blob/main/browser/src/map/handler/Map.WOPI.js),
  and [locale resources](https://github.com/CollaboraOnline/online.mirror/tree/main/browser/po).
  Active development moved to Collabora Gerrit; `online.mirror` is read-only.
- Tiptap [conversion overview](https://tiptap.dev/docs/conversion/getting-started/overview)
  and docx-preview [package metadata](https://github.com/VolodymyrBaydalka/docxjs/blob/master/package.json).

### E00.3–E00.5 proof contract

Proceed with the permitted custom prototype because no evaluated ready-made route
has established the whole required integration within the accepted stack/license
boundary. This is not a claim that no free Word editor exists. Do not supersede
D008 or mark E00 done until runtime evidence passes.

Use original OOXML parts as canonical source, with stable paragraph/run/control
identities mapped to a typed editable model. Transactions must support direct
surrounding edits and editable field content. Sidebar values derive from that same
state, including linked occurrences, selection, deletion and undo/redo. Export
applies validated changes to mapped package nodes and retains untouched package
parts; rebuilding from extracted text or rendered HTML is disallowed.

E00.3 proves field creation, both synchronization directions, navigation and locale
switching against the synthetic Ukrainian corpus. E00.4 proves surrounding edits,
control deletion, repeated occurrences, undo/redo, original preservation, export
and independent reopen. Include split runs, tables, headers/footers, numbering,
Unicode and long values. Unsupported structures must be explicit and unchanged;
reject edits that cannot be safely mapped. E00.5 records exact locked packages,
notices, browser and structural results, visual comparisons and any real limitations.
Keep Microsoft Word verification distinct from LibreOffice or self-reopening.
No owner-level licensing choice or product narrowing is needed for this prototype;
if its evidence shows one is unavoidable, record that concrete gap and continue
independent account/storage tasks while seeking the smallest decision.

## E00.3 implementation and scope

The prototype is a reusable `frontend/src/editor/DocumentEditor.tsx` with
ProseMirror schema/transaction modules and a Python `DocxPackage` importer under
`backend/app/documents`. The development-only `/prototype.html` harness loads a
model generated directly from the immutable DOCX fixture. Its answer key is never
an importer input; CI regenerates the model and rejects drift. Vite's production
entry does not include the harness or fixture. No unauthenticated document API or
retained-file write was introduced.

The importer retains original bytes and every package part, bounds archive/expanded
size and entries, rejects DTD/entity input, and maps paragraphs/runs/tables/native
plain-text controls. Existing native control IDs are part-scoped and remain stable
when surrounding XML nodes are inserted; other source anchors are revision-local.
Duplicate control IDs fail; absent/blank tags do not link unrelated controls. Complex
or unknown structures remain explicit locked nodes rather than editable text copies.
Original identities/styles survive model-to-DOM-to-model parsing, including spaces.
This is editable source mapping, not a claim of complete DOCX format validation (E03)
or export/reopen support (E00.4).

Field selection-to-creation, shared-key sidebar updates, direct control typing and
focus navigation use one editor transaction state. Direct native typing required an
explicit field input handler: otherwise Chrome could remove an inline control when
replacing all its text. Ambiguous linked values stay visible for review. Locale
updates change labels/attributes without reconstructing the editor or undo history.
Local field identifiers use `crypto.getRandomValues`, which works at the agreed HTTP
origin; they do not depend on HTTPS-only `randomUUID` availability.

Locked npm versions: model 1.25.4, state 1.4.4, view 1.41.7, commands 1.7.1,
history 1.5.0, keymap 1.2.3, transform 1.12.1, orderedmap 2.1.1, rope-sequence 1.3.4,
and w3c-keyname 2.2.8. All ten installed package licenses were inspected as MIT;
`frontend/public/editor-notices.txt` retains their full notices in static assets.
The required notice-regeneration check detects changes. Python's defusedxml 0.7.1
is hash-locked and its installed distribution retains its license. These obligations
do not change Fillable's undecided project license.

E00.3 browser proof covers the real Ukrainian corpus: both native client-name
occurrences update from the sidebar and from native typing; focus reaches the field;
a selection across the email token's styled runs becomes a new field; switching to
English preserves that draft and editor instance; undo/redo still works. Unit tests
also cover ambiguous linked changes, invalid/cross-field selections, empty values,
DOM source/whitespace preservation and importer failure boundaries.

The browser currently presents a structural editing canvas with basic emphasis,
alignment and tables, not Word pagination. Headers/footers are separate editable
parts, and complex PAGE instructions are locked. No claim is made yet about exported
formatting, structural additions, deletion/reopen or full input-composition behavior.
E00.4 and E00.5 must establish the save/reopen/visual support matrix; E05 completes
production workspace behavior. D008 is still provisional.

## E00.4 round-trip proof

The opt-in `compose.editor-proof.yaml` adds only the synthetic development API;
normal development and production run `app.main` and return 404 for these routes.
`/prototype.html` now loads the corpus through this opt-in API. All parsing,
validation, export and reopening run in Python, entirely in bounded memory. No
user-retained filesystem write or quota bypass is introduced. Browser downloads and
render reports are synthetic QA artifacts. Production save APIs remain E06 work.

The adapter now uses hash-locked BSD-licensed lxml 6.1.3, with entity resolution,
DTD loading, networking, recovery and huge-tree mode disabled. DTD input is rejected.
Its namespace-preserving serializer retains compatibility prefix declarations.
This replaces E00.3's defusedxml dependency; installed lxml distribution notices
remain included. No editor dependency or project license changes.

Exports require the exact source digest. Known source anchors, immutable styling
metadata, container membership and locked nodes are validated before output.
Unchanged exports return the exact original ZIP bytes. Changed exports preserve
untouched ZIP member bytes and metadata; unchanged XML subtrees remain intact.
Source paragraph/run properties, table geometry, numbering, headers/footers and
unsupported content are retained. No global replacement, HTML conversion or
extracted-text reconstruction is used. New controls receive native numeric IDs,
and field labels/keys retain their Unicode. New paragraph IDs are distinct both
in the editor and OOXML. Newline/tab text is represented by Word breaks/tabs.

Verified scope: direct text edits; paragraph splitting/deletion within existing
containers; selection-created plain-text controls; linked value updates; empty
values; removing a control while retaining its text; undo/redo; DOCX download and
explicit editor reopening. Existing control IDs survive reopening; new field keys
survive their conversion to native control IDs. Repeated identical text elsewhere
is not substituted. Stale revisions, unknown anchors, altered source styling,
invalid/nested controls, removal of locked content and section-boundary deletion
are rejected. Bound, locked or temporary native controls are protected. Page/column
breaks and other unsupported objects remain locked.

The editor remains a structural canvas, not a Word layout engine. Table row/cell
creation, arbitrary formatting commands, complex controls, tracked-change editing,
IME/composition and general Word feature compatibility are not established by this
proof. Existing complex structures are preserved or protected. E05/E06 must retain
these restrictions visibly and handle save errors without losing drafts. Microsoft
Word itself has not been used for validation; LibreOffice rendering and embedded
editor reopening are separate evidence.

Independent visual QA uses the pinned QA-only `infra/docx-proof.Dockerfile`
(LibreOffice Writer 7.4.7 Debian update 14, Poppler 22.12.0 Debian update 3,
Liberation fonts 1.07.4), never the application image. Run
`scripts/verify-docx-render.sh <browser-results-directory>` after the fresh-index
harness. The three original/unchanged-export pages match pixel-for-pixel at the
same rendering size, and unchanged DOCX bytes match exactly. The edited fixture
retains three pages; page two matches exactly, both table XML subtrees are unchanged,
and the intended title paragraph and client-name edits render correctly. All six
original/edited pages were visually inspected for clipping, layout and Unicode.
The browser's downloaded files, reopened screenshot, PDF pages and extracted text
are retained as CI QA artifacts. D008's adoption decision remains E00.5.

## E00.5 adoption and support matrix

Decision: **go** with the project-owned ProseMirror editor and Python source-package
adapter for the MVP. E00.3/E00.4 establish the required editable field workflow and
DOCX round trip on the synthetic Ukrainian corpus. This is an engineering choice
within the already accepted free-only/custom-implementation option, with no new fee,
service, project-license decision or product-page change.

| Capability | Verified result | Boundary carried into production work |
| --- | --- | --- |
| Native field import/identity | Five native occurrences, including linked client names, map to stable part-scoped control IDs | Malformed/duplicate identities fail; revision-local run/paragraph anchors require matching source digest |
| Field creation | A real selection across styled Cyrillic runs becomes a control, exports and reopens with its label/key/value | Plain text within one paragraph; invalid/cross-control selections fail visibly |
| Sidebar and direct editing | Both native occurrences update in both directions; focus selects the correct control | Ambiguous linked values remain visible for review; no global same-text replacement |
| Surrounding text | Direct typing, paragraph split/deletion and source formatting export/reopen | Existing table containers remain fixed; new paragraph IDs are distinct in editor and OOXML |
| Control removal and history | Removal keeps text, undo restores the control, redo removes it; exported state reopens | Production version history is E06, distinct from transient editor undo |
| Unicode and whitespace | Ґ/Є/І/Ї, apostrophes, mixed scripts, spaces, tabs and multiline values survive | No transliteration or document translation; broader IME/composition acceptance is E05/E07 |
| Source preservation | No-edit bytes identical; untouched package parts, table subtrees and paragraph properties retained | Locked/unknown structures cannot be removed or rewritten; source revision is mandatory |
| Independent rendering | Three original/export pages match; edited file remains three pages, with intended changes and untouched page two identical | LibreOffice/Poppler evidence; no Microsoft Word test or universal layout guarantee |
| UI localization | Exposed controls/accessibility text use uk/en catalogs; language switch preserves draft and editor history | Account-persisted preference is E02.7; locale never changes document values |
| Production footprint | Browser libraries plus existing Python backend; no editor server, Node business runtime or conversion service | Development proof routes stay opt-in; production ownership/quota/save routes remain E03/E06 |

The locked browser packages are ProseMirror model 1.25.4, state 1.4.4, view 1.41.7,
commands 1.7.1, history 1.5.0, keymap 1.2.3, transform 1.12.1, orderedmap 2.1.1,
rope-sequence 1.3.4 and w3c-keyname 2.2.8. All ten are MIT and their complete notices
are generated into the distributed static asset and drift-checked by CI. The Python
XML component is BSD-licensed lxml 6.1.3 with installed distribution/dependency
notices retained. The QA-only LibreOffice/Poppler image has no production role and
is not the canonical export path. Fillable's own license remains undecided.

Explicitly protected/unproved features include page/column breaks, complex fields,
XML-bound or locked controls, drawings/unknown OOXML, tracked-change editing,
arbitrary table structure/formatting changes and exact Word pagination in the
browser. Preserve these features or reject the attempted operation; never silently
flatten them. The UI is a structural editing canvas. These boundaries do not remove
required ordinary text editing, field creation, synchronization, undo/redo or DOCX
export, which have actual end-to-end proof.

Production adoption requires reusing this source revision/anchor contract. E03
adds upload/package validation and ownership; E04 produces validated detector
locations; E05 integrates the editor and input behavior; E06 makes immutable
file/field revisions and quota-backed writes atomic, with failed-save draft retention
and explicit restore/reopen choices. E07 tests complete user flows. E00's go decision
is not a claim those application tasks are already implemented or permission for
early deployment. Revisit the support matrix when adding a new OOXML feature or
reviewed real fixture, preserving the immutable v1 corpus.
