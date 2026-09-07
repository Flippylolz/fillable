import { EditorState, type Transaction } from "prosemirror-state";
import { EditorView } from "prosemirror-view";
import { history, undo, redo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { baseKeymap } from "prosemirror-commands";
import type { components } from "../../generated/api";
import { editorSchema, fields, type FieldOccurrence } from "./model";
import { collapseFieldSelection, createField, fieldBeforeInput, fieldLineBreak, fieldPaste, fieldTextInput, focusField, linkedChanges, manualFieldIssue, newFieldId, paragraphIdentities, removeField, retainComposedField, updateField } from "./transactions";
import { attachReview, configureCandidate, focusCandidate, reviewCandidate, reviewChanges, reviewState, type ReviewState } from "./review";
import { fieldValueIssue, type FieldValueIssue } from "./fieldValues";

export type FieldSummary = Pick<FieldOccurrence, "id" | "key" | "label" | "value"> & { issue: FieldValueIssue };
export type ReviewAction = "accept" | "dismiss" | "configure" | "focus";
export type ReviewOptions = { label: string; key: string; type: string };
export type EditorPresentation = { fields: FieldSummary[]; active: string; review: ReviewState | null; unsupported: boolean; fieldValuesValid: boolean; composing: boolean };
export type EditorSnapshot = { document: object; revision: number; fieldValuesValid: boolean; composing: boolean };

/** The mounted editor owns document state. Callers receive detached snapshots only. */
export function mountEditor(host: HTMLElement, initialDocument: object, callbacks: {
  canEdit?: () => boolean;
  onChange: (snapshot: EditorSnapshot) => void;
  onUpdate: (presentation: EditorPresentation) => void;
}) {
  const source = editorSchema.nodeFromJSON(structuredClone(initialDocument));
  let revision = 0, unsupported = false, settling = false;
  const allowed = () => callbacks.canEdit?.() !== false;
  let compositionSource: EditorState | null = null;
  let compositionChanges: Transaction | null = null;
  let compositionId: number | undefined;
  let compositionTimer: ReturnType<typeof setTimeout> | undefined;
  source.descendants(node => { if (node.type.name.startsWith("locked")) unsupported = true; });
  const editor = new EditorView(host, {
    editable: () => allowed() || compositionSource !== null,
    state: EditorState.create({ schema: editorSchema, doc: source,
      plugins: [history(), keymap({ "Mod-z": undo, "Mod-Shift-z": redo, "Mod-y": redo, Enter: fieldLineBreak, "Shift-Enter": fieldLineBreak,
        ArrowRight: collapseFieldSelection(true), ArrowLeft: collapseFieldSelection(false) }), keymap(baseKeymap)],
    }),
    handleTextInput: (view, from, to, value) => !allowed() && !compositionSource || fieldTextInput(view, from, to, value),
    handleDOMEvents: {
      beforeinput(view, event) {
        if (!allowed() && !compositionSource) { event.preventDefault(); return true; }
        return fieldBeforeInput(view, event);
      },
      compositionstart(_view, event) {
        if (!allowed()) { event.preventDefault(); return true; }
        finishComposition();
        compositionSource = editor.state;
        compositionChanges = editor.state.tr;
        compositionId = undefined;
        publish();
        return false;
      },
      compositionend() {
        // The pinned view settles composition/queued DOM mutations after 20 ms.
        // Synchronize only after that flush, including unchanged final candidates.
        compositionTimer = setTimeout(finishComposition, 25);
        return false;
      },
    },
    handlePaste: (view, event) => !allowed() || fieldPaste(view, event),
    dispatchTransaction(transaction: Transaction) {
      if (transaction.docChanged && !transaction.getMeta("review-initial") && !allowed() && !compositionSource && !settling) { editor.updateState(editor.state); return; }
      if (compositionSource && typeof transaction.getMeta("composition") === "number") compositionId = transaction.getMeta("composition");
      const transformed = paragraphIdentities(compositionSource ? transaction : linkedChanges(editor.state, transaction));
      if (compositionChanges) for (const step of transformed.steps) compositionChanges.step(step);
      const next = editor.state.apply(compositionSource ? transformed : reviewChanges(editor.state, transformed));
      editor.updateState(next);
      if (transaction.docChanged && !transaction.getMeta("review-initial")) {
        revision += 1;
        callbacks.onChange(exportSnapshot());
      }
      publish();
    },
  });
  function finishComposition() {
    clearTimeout(compositionTimer);
    const source = compositionSource;
    const changes = compositionChanges;
    compositionSource = null;
    compositionChanges = null;
    if (!source) return;
    if (source.doc.eq(editor.state.doc)) { editor.setProps({}); publish(); return; }
    const transaction = linkedChanges(source, retainComposedField(source, editor.state.tr, changes!.mapping), true);
    for (const step of transaction.steps) changes!.step(step);
    const review = reviewState(reviewChanges(source, changes!).doc);
    if (review !== reviewState(editor.state.doc)) transaction.setDocAttribute("review", review);
    if (transaction.docChanged) {
      if (compositionId !== undefined) transaction.setMeta("composition", compositionId);
      settling = true;
      try { editor.dispatch(transaction); } finally { settling = false; }
    } else publish();
    editor.setProps({});
  }
  function exportSnapshot(): EditorSnapshot {
    return { document: structuredClone(editor.state.doc.toJSON()), revision, composing: compositionSource !== null,
      fieldValuesValid: fields(editor.state.doc).every(field => fieldValueIssue(field.value) === null) };
  }
  function publish() {
    const occurrences = fields(editor.state.doc);
    const active = occurrences.find(field => editor.state.selection.from > field.pos && editor.state.selection.from < field.pos + field.size)?.id ?? "";
    const summaries = occurrences.map(({ id, key, label, value }) => ({ id, key, label, value, issue: fieldValueIssue(value) }));
    callbacks.onUpdate({ fields: summaries, fieldValuesValid: summaries.every(field => field.issue === null),
      active, review: structuredClone(reviewState(editor.state.doc)), unsupported, composing: compositionSource !== null });
  }
  function dispatch(transaction: Transaction | null, focus = false): boolean {
    if (!transaction || (transaction.docChanged && !allowed())) return false;
    editor.dispatch(transaction);
    if (focus) editor.focus();
    return true;
  }
  publish();
  return {
    exportSnapshot,
    refreshAccess() { editor.setProps({}); },
    setDocumentLabel(label: string) {
      editor.setProps({ attributes: { "aria-label": label, role: "textbox", "aria-multiline": "true" } });
    },
    attachDiscovery(snapshot: components["schemas"]["FieldSnapshot"], sourceVersion: string): boolean {
      if (compositionSource) return false;
      const current = reviewState(editor.state.doc);
      if (current) return current.sourceVersion !== null;
      try {
        if (!editor.state.doc.content.eq(source.content)) return false;
        const attached = attachReview(editor.state.doc, snapshot, sourceVersion);
        editor.dispatch(editor.state.tr.setDocAttribute("review", reviewState(attached))
          .setMeta("review-initial", true).setMeta("addToHistory", false));
        return true;
      } catch { return false; }
    },
    review(id: string, action: ReviewAction, options: ReviewOptions): boolean {
      const transaction = action === "focus" ? focusCandidate(editor.state, id)
        : action === "configure" ? configureCandidate(editor.state, id, options.label, options.key || newFieldId(), options.type)
        : reviewCandidate(editor.state, id, action, { ...options, key: options.key || undefined });
      return dispatch(transaction, action === "focus" || action === "accept");
    },
    createField(label: string) {
      if (!allowed()) return "read_only" as const;
      const issue = manualFieldIssue(editor.state, label);
      if (!issue) dispatch(createField(editor.state, label, newFieldId()), true);
      return issue;
    },
    updateField(key: string, value: string) {
      const transaction = updateField(editor.state, key, value);
      return transaction.docChanged && dispatch(transaction);
    },
    focusField(id: string) { return dispatch(focusField(editor.state, id), true); },
    removeField(id: string) { return dispatch(removeField(editor.state, id)); },
    undo() { if (!allowed()) return false; const changed = undo(editor.state, editor.dispatch); editor.focus(); return changed; },
    redo() { if (!allowed()) return false; const changed = redo(editor.state, editor.dispatch); editor.focus(); return changed; },
    destroy() { clearTimeout(compositionTimer); editor.destroy(); },
  };
}

export type EditorAdapter = ReturnType<typeof mountEditor>;
