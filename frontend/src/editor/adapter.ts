import { EditorState, type Transaction } from "prosemirror-state";
import { EditorView } from "prosemirror-view";
import { history, undo, redo } from "prosemirror-history";
import { keymap } from "prosemirror-keymap";
import { baseKeymap } from "prosemirror-commands";
import type { components } from "../../generated/api";
import { editorSchema, fields, type FieldOccurrence } from "./model";
import { createField, fieldBeforeInput, fieldPaste, fieldTextInput, focusField, linkedChanges, manualFieldIssue, newFieldId, paragraphIdentities, removeField, updateField } from "./transactions";
import { attachReview, configureCandidate, focusCandidate, reviewCandidate, reviewChanges, reviewState, type ReviewState } from "./review";
import { fieldValueIssue, type FieldValueIssue } from "./fieldValues";

export type FieldSummary = Pick<FieldOccurrence, "id" | "key" | "label" | "value"> & { issue: FieldValueIssue };
export type ReviewAction = "accept" | "dismiss" | "configure" | "focus";
export type ReviewOptions = { label: string; key: string; type: string };
export type EditorPresentation = { fields: FieldSummary[]; active: string; review: ReviewState | null; unsupported: boolean; fieldValuesValid: boolean };
export type EditorSnapshot = { document: object; revision: number; fieldValuesValid: boolean };

/** The mounted editor owns document state. Callers receive detached snapshots only. */
export function mountEditor(host: HTMLElement, initialDocument: object, callbacks: {
  onChange: (snapshot: EditorSnapshot) => void;
  onUpdate: (presentation: EditorPresentation) => void;
}) {
  const source = editorSchema.nodeFromJSON(structuredClone(initialDocument));
  let revision = 0, unsupported = false;
  source.descendants(node => { if (node.type.name.startsWith("locked")) unsupported = true; });
  const editor = new EditorView(host, {
    state: EditorState.create({ schema: editorSchema, doc: source,
      plugins: [history(), keymap({ "Mod-z": undo, "Mod-Shift-z": redo, "Mod-y": redo }), keymap(baseKeymap)],
    }),
    handleTextInput: fieldTextInput,
    handleDOMEvents: { beforeinput: fieldBeforeInput },
    handlePaste: fieldPaste,
    dispatchTransaction(transaction: Transaction) {
      const next = editor.state.apply(reviewChanges(editor.state, paragraphIdentities(linkedChanges(editor.state, transaction))));
      editor.updateState(next);
      if (transaction.docChanged && !transaction.getMeta("review-initial")) {
        revision += 1;
        callbacks.onChange(exportSnapshot());
      }
      publish();
    },
  });
  function exportSnapshot(): EditorSnapshot {
    return { document: structuredClone(editor.state.doc.toJSON()), revision,
      fieldValuesValid: fields(editor.state.doc).every(field => fieldValueIssue(field.value) === null) };
  }
  function publish() {
    const occurrences = fields(editor.state.doc);
    const active = occurrences.find(field => editor.state.selection.from > field.pos && editor.state.selection.from < field.pos + field.size)?.id ?? "";
    const summaries = occurrences.map(({ id, key, label, value }) => ({ id, key, label, value, issue: fieldValueIssue(value) }));
    callbacks.onUpdate({ fields: summaries, fieldValuesValid: summaries.every(field => field.issue === null),
      active, review: structuredClone(reviewState(editor.state.doc)), unsupported });
  }
  function dispatch(transaction: Transaction | null, focus = false): boolean {
    if (!transaction) return false;
    editor.dispatch(transaction);
    if (focus) editor.focus();
    return true;
  }
  publish();
  return {
    exportSnapshot,
    setDocumentLabel(label: string) {
      editor.setProps({ attributes: { "aria-label": label, role: "textbox", "aria-multiline": "true" } });
    },
    attachDiscovery(snapshot: components["schemas"]["FieldSnapshot"], sourceVersion: string): boolean {
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
      const issue = manualFieldIssue(editor.state, label);
      if (!issue) dispatch(createField(editor.state, label, newFieldId()), true);
      return issue;
    },
    updateField(key: string, value: string) { return dispatch(updateField(editor.state, key, value)); },
    focusField(id: string) { return dispatch(focusField(editor.state, id), true); },
    removeField(id: string) { return dispatch(removeField(editor.state, id)); },
    undo() { const changed = undo(editor.state, editor.dispatch); editor.focus(); return changed; },
    redo() { const changed = redo(editor.state, editor.dispatch); editor.focus(); return changed; },
    destroy() { editor.destroy(); },
  };
}

export type EditorAdapter = ReturnType<typeof mountEditor>;
