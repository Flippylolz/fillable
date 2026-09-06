# Free editor feasibility

Status: research notes for E00, checked 2026-09-06. The user requires free solutions and permits a project-owned implementation. No runtime evaluation, editor selection, or compatibility proof has been completed.

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
