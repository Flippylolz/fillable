import type { Node as EditorNode } from "prosemirror-model";
import type { EditorState } from "prosemirror-state";
import { closeHistory } from "prosemirror-history";
import { fields } from "./model";

export const textFormats = ["bold", "italic", "underline"] as const;
export type TextFormat = typeof textFormats[number];

function enabled(node: EditorNode, format: TextFormat): boolean {
  const override = node.marks.find(mark => mark.type.name === "format")?.attrs[format];
  return override ?? node.marks.find(mark => mark.type.name === "source")?.attrs[format] ?? false;
}

/** Explicit formatting overrides preserve immutable source-run identities. */
export function formatText(state: EditorState, format: TextFormat, key?: string) {
  const ranges = key === undefined ? [{ from: state.selection.from, to: state.selection.to }]
    : fields(state.doc).filter(field => field.key === key).map(field => ({ from: field.pos + 1, to: field.pos + 1 + field.size - 2 }));
  const spans: { node: EditorNode; from: number; to: number }[] = [];
  for (const range of ranges.filter(range => range.to > range.from)) state.doc.nodesBetween(range.from, range.to, (node, pos) => {
    if (node.isText) spans.push({ node, from: Math.max(pos, range.from), to: Math.min(pos + node.nodeSize, range.to) });
  });
  if (!spans.length) return null;
  const value = !spans.every(span => enabled(span.node, format));
  const transaction = state.tr;
  for (const span of spans) {
    const previous = span.node.marks.find(mark => mark.type.name === "format");
    transaction.addMark(span.from, span.to, state.schema.marks.format.create({ ...previous?.attrs, [format]: value }));
  }
  return closeHistory(transaction);
}
