import {
  TextSelection,
  type EditorState,
  type Command,
  type Transaction,
} from "prosemirror-state";
import { closeHistory, isHistoryTransaction } from "prosemirror-history";
import { fields } from "./model";
import type { EditorView } from "prosemirror-view";
import { FIELD_LABEL_LIMIT, FIELD_RECORD_LIMIT, validFieldProperty } from "./fieldProperties";
import type { Node as EditorNode } from "prosemirror-model";

export function collapseFieldSelection(forward: boolean): Command {
  return (state, dispatch) => {
    const { $from, $to, empty, from, to } = state.selection;
    if (empty || $from.parent.type.name !== "field" || $from.parent !== $to.parent) return false;
    dispatch?.(state.tr.setSelection(TextSelection.create(state.doc, forward ? to : from)));
    return true;
  };
}

// A fast native IME commit may unwrap the selected inline control in the DOM.
// Restore only its mapped text range and original identity, never matching text elsewhere.
export function retainComposedField(source: EditorState, transaction: Transaction, mapping: Pick<Transaction["mapping"], "map">): Transaction {
  const { $from, $to } = source.selection;
  if ($from.parent.type.name !== "field" || $from.parent !== $to.parent) return transaction;
  const original = $from.parent;
  if (fields(transaction.doc).some(field => field.id === original.attrs.id)) return transaction;
  const from = mapping.map($from.before(), -1), to = mapping.map($from.after(), 1);
  const start = transaction.doc.resolve(from), end = transaction.doc.resolve(to);
  if (start.parent !== end.parent || start.parent.type.name !== "paragraph") return transaction;
  let blocked = false;
  transaction.doc.nodesBetween(from, to, node => { if (node.isInline && !node.isText) blocked = true; });
  if (blocked) return transaction;
  const content: EditorNode[] = [];
  transaction.doc.slice(from, to).content.forEach(node => content.push(node.marks.length ? node : node.mark(original.firstChild?.marks ?? [])));
  return transaction.replaceWith(from, to, original.type.create(original.attrs, content, original.marks));
}

export const fieldLineBreak: Command = (state, dispatch) => {
  const { $from, $to } = state.selection;
  if ($from.parent.type.name !== "field" || $from.parent !== $to.parent) return false;
  dispatch?.(state.tr.insertText("\n").scrollIntoView());
  return true;
};

export function fieldTextInput(
  editor: Pick<EditorView, "state" | "dispatch"> & { composing?: boolean },
  _from: number,
  _to: number,
  value: string,
): boolean {
  if (editor.composing) return false;
  const { $from, $to } = editor.state.selection;
  if ($from.parent.type.name !== "field" || $from.parent !== $to.parent)
    return false;
  editor.dispatch(editor.state.tr.insertText(value));
  return true;
}

// Native multiline insertion can replace the control's DOM wrapper before DOM parsing.
// Apply it while the verified editor selection is still inside the same field.
export function fieldBeforeInput(editor: Pick<EditorView, "state" | "dispatch">, event: Event): boolean {
  const input = event as InputEvent;
  if (input.isComposing) return false;
  const value = input.inputType === "insertParagraph" || input.inputType === "insertLineBreak" ? "\n"
    : input.inputType === "insertText" || input.inputType === "insertReplacementText" ? input.data : null;
  if (value === null || !/[\n\r\t]/.test(value)) return false;
  if (!fieldTextInput(editor, editor.state.selection.from, editor.state.selection.to, value)) return false;
  event.preventDefault();
  return true;
}

export function fieldPaste(editor: Pick<EditorView, "state" | "dispatch">, event: ClipboardEvent): boolean {
  const value = event.clipboardData?.getData("text/plain");
  return !!value && fieldTextInput(editor, editor.state.selection.from, editor.state.selection.to, value);
}

// getRandomValues is available at the accepted HTTP origin as well as HTTPS.
export function newFieldId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export function updateField(
  state: EditorState,
  key: string,
  value: string,
): Transaction {
  const transaction = closeHistory(state.tr);
  for (const occurrence of fields(state.doc)
    .filter((field) => field.key === key && field.value !== value)
    .reverse()) {
    const start = occurrence.pos + 1;
    const marks = state.doc.nodeAt(start)?.marks;
    transaction.replaceWith(
      start,
      occurrence.pos + occurrence.size - 1,
      value ? state.schema.text(value, marks) : [],
    );
  }
  return transaction.setMeta("field-update", true);
}

export type ManualFieldIssue = "invalid_label" | "invalid_selection" | "field_limit" | null;
export function manualFieldIssue(state: EditorState, label: string): ManualFieldIssue {
  if (!validFieldProperty(label.trim(), FIELD_LABEL_LIMIT)) return "invalid_label";
  if (fields(state.doc).length >= FIELD_RECORD_LIMIT || (state.doc.attrs.review?.items.length ?? 0) >= FIELD_RECORD_LIMIT) return "field_limit";
  const { from, to, $from, $to, empty } = state.selection;
  if (
    empty ||
    $from.parent !== $to.parent ||
    $from.parent.type.name !== "paragraph"
  )
    return "invalid_selection";
  let blocked = false;
  state.doc.nodesBetween(from, to, (node) => {
    if (node.isInline && !node.isText) blocked = true;
  });
  return blocked ? "invalid_selection" : null;
}

export function createField(
  state: EditorState,
  label: string,
  id: string,
): Transaction | null {
  if (manualFieldIssue(state, label)) return null;
  const { from, to } = state.selection;
  const field = state.schema.nodes.field.create(
    { id, key: id, label: label.trim() },
    state.doc.slice(from, to).content,
  );
  const transaction = closeHistory(state.tr).replaceWith(from, to, field);
  return transaction.setSelection(
    TextSelection.create(transaction.doc, from + 1),
  );
}

export function focusField(state: EditorState, id: string): Transaction | null {
  const matches = fields(state.doc).filter(field => field.id === id);
  const occurrence = matches.length === 1 ? matches[0] : null;
  return occurrence
    ? state.tr
        .setSelection(
          TextSelection.create(
            state.doc,
            occurrence.pos + 1,
            occurrence.pos + occurrence.size - 1,
          ),
        )
        .scrollIntoView()
    : null;
}

export function linkedChanges(
  state: EditorState,
  transaction: Transaction,
  compositionCommit = false,
): Transaction {
  if ((!transaction.docChanged && !compositionCommit) || transaction.getMeta("field-update") || isHistoryTransaction(transaction))
    return transaction;
  const previous = new Map(
    fields(state.doc).map((field) => [field.id, field.value]),
  );
  const current = fields(transaction.doc);
  const changed = current.filter(
    (field) => previous.has(field.id) && previous.get(field.id) !== field.value,
  );
  const keys = new Set(changed.map((field) => field.key));
  for (const key of keys) {
    const values = new Set(
      changed.filter((field) => field.key === key).map((field) => field.value),
    );
    // Ambiguous changes remain visibly inconsistent for review; never pick a winner.
    if (values.size !== 1) continue;
    const value = [...values][0];
    for (const field of fields(transaction.doc)
      .filter((field) => field.key === key && field.value !== value)
      .reverse()) {
      transaction.replaceWith(
        field.pos + 1,
        field.pos + field.size - 1,
        value
          ? state.schema.text(
              value,
              transaction.doc.nodeAt(field.pos + 1)?.marks,
            )
          : [],
      );
    }
  }
  return transaction;
}

export function paragraphIdentities(transaction: Transaction): Transaction {
  if (!transaction.docChanged) return transaction;
  const seen = new Set<string>();
  let previous: string | null = null;
  transaction.doc.descendants((node, pos) => {
    if (node.type.name !== "paragraph") return;
    const id = node.attrs.id as string | null;
    if (!id || seen.has(id)) {
      const source = id ?? previous;
      if (source) {
        const base = source.startsWith("new:")
          ? source.slice(4, source.lastIndexOf(":"))
          : source;
        transaction.setNodeMarkup(pos, undefined, {
          ...node.attrs,
          id: `new:${base}:${newFieldId()}`,
        });
      }
    }
    if (id) {
      seen.add(id);
      previous = id;
    }
  });
  return transaction;
}

export function removeField(
  state: EditorState,
  id: string,
): Transaction | null {
  const matches = fields(state.doc).filter(field => field.id === id);
  if (matches.length !== 1) return null;
  const occurrence = matches[0];
  const node = state.doc.nodeAt(occurrence.pos)!;
  return closeHistory(state.tr).replaceWith(
    occurrence.pos,
    occurrence.pos + occurrence.size,
    node.content,
  );
}
