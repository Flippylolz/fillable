import {
  TextSelection,
  type EditorState,
  type Transaction,
} from "prosemirror-state";
import { closeHistory, isHistoryTransaction } from "prosemirror-history";
import { fields } from "./model";
import type { EditorView } from "prosemirror-view";

export function fieldTextInput(
  editor: Pick<EditorView, "state" | "dispatch">,
  _from: number,
  _to: number,
  value: string,
): boolean {
  const { $from, $to } = editor.state.selection;
  if ($from.parent.type.name !== "field" || $from.parent !== $to.parent)
    return false;
  editor.dispatch(editor.state.tr.insertText(value));
  return true;
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
    .filter((field) => field.key === key)
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

export function createField(
  state: EditorState,
  label: string,
  id: string,
): Transaction | null {
  const { from, to, $from, $to, empty } = state.selection;
  if (
    empty ||
    $from.parent !== $to.parent ||
    $from.parent.type.name !== "paragraph" ||
    !label.trim()
  )
    return null;
  let blocked = false;
  state.doc.nodesBetween(from, to, (node) => {
    if (node.isInline && !node.isText) blocked = true;
  });
  if (blocked) return null;
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
  const occurrence = fields(state.doc).find((field) => field.id === id);
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
): Transaction {
  if (!transaction.docChanged || transaction.getMeta("field-update") || isHistoryTransaction(transaction))
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
  const occurrence = fields(state.doc).find((field) => field.id === id);
  if (!occurrence) return null;
  const node = state.doc.nodeAt(occurrence.pos)!;
  return closeHistory(state.tr).replaceWith(
    occurrence.pos,
    occurrence.pos + occurrence.size,
    node.content,
  );
}
