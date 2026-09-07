import type { Node as EditorNode } from "prosemirror-model";
import { TextSelection, type EditorState, type Transaction } from "prosemirror-state";
import { closeHistory } from "prosemirror-history";
import type { components } from "../../generated/api";
import { fields, type FieldOccurrence } from "./model";
import { newFieldId } from "./transactions";
import { validFieldProperty } from "./fieldProperties";

type Snapshot = components["schemas"]["FieldSnapshot"];
type Candidate = components["schemas"]["Candidate"];
export type ReviewItem = {
  id: string;
  occurrenceId: string;
  reason: Candidate["reason"];
  sourceKey: string | null;
  context: string;
  label: string;
  key: string;
  type: "text";
  decision: "proposed" | "accepted" | "dismissed";
  missing: boolean;
  location: { kind: "span"; from: number; to: number; text: string }
    | { kind: "control"; id: string };
};
export type ReviewState = { sourceVersion: string | null; items: ReviewItem[] };
export function reviewState(doc: EditorNode): ReviewState | null {
  return doc.attrs.review;
}

function controls(doc: EditorNode): Map<string, FieldOccurrence> {
  const result = new Map<string, FieldOccurrence>();
  const duplicates = new Set<string>();
  for (const field of fields(doc)) {
    if (result.has(field.id)) duplicates.add(field.id);
    result.set(field.id, field);
  }
  for (const id of duplicates) result.delete(id);
  return result;
}

function allowedSpan(doc: EditorNode, from: number, to: number, text: string): boolean {
  if (from < 0 || from > to || to > doc.content.size) return false;
  const start = doc.resolve(from), end = doc.resolve(to);
  if (start.parent !== end.parent || start.parent.type.name !== "paragraph") return false;
  if (from === to) return start.parent.content.size === 0 && text === "";
  let blocked = false;
  doc.nodesBetween(from, to, node => { if (node.isInline && !node.isText) blocked = true; });
  return !blocked && doc.textBetween(from, to) === text;
}

// Python offsets count code points; ProseMirror positions count UTF-16 and node tokens.
function paragraphs(doc: EditorNode) {
  const result = new Map<string, { pos: number; chars: string[]; points: [number, number][] }>();
  doc.forEach((section, sectionOffset) => section.descendants((node, relative) => {
    if (node.type.name !== "paragraph") return;
    const key = JSON.stringify([section.attrs.part, node.attrs.id]);
    if (result.has(key)) throw new Error("invalid_review");
    const pos = sectionOffset + 1 + relative;
    const chars: string[] = [], points: [number, number][] = [];
    node.forEach((child, offset) => {
      let position = pos + 1 + offset + (child.type.name === "field" ? 1 : 0);
      for (const char of child.isText || child.type.name === "field" ? child.textContent : "\ufffc") {
        chars.push(char);
        points.push([position, position + char.length]);
        position += char.length;
      }
    });
    result.set(key, { pos, chars, points });
    return false;
  }));
  return result;
}

export function attachReview(doc: EditorNode, snapshot: Snapshot, sourceVersion: string): EditorNode {
  if (snapshot.schema_version !== 1 || snapshot.source_version_id !== sourceVersion || reviewState(doc))
    throw new Error("invalid_review");
  const candidates = snapshot.candidates ?? [], occurrences = snapshot.occurrences ?? [];
  const indexed = paragraphs(doc), native = controls(doc);
  const locations = new Map(occurrences.map(item => [item.id, item]));
  const decisions = new Map((snapshot.decisions ?? []).map(item => [item.candidate_id, item.status]));
  if (candidates.length > 2000 || occurrences.length > 2000 || locations.size !== occurrences.length
    || new Set(candidates.map(item => item.id)).size !== candidates.length
    || new Set(candidates.map(item => item.occurrence_id)).size !== candidates.length)
    throw new Error("invalid_review");
  const items: ReviewItem[] = candidates.map(candidate => {
    const occurrence = locations.get(candidate.occurrence_id);
    if (!occurrence) throw new Error("invalid_review");
    const anchor = occurrence.anchor;
    const paragraph = indexed.get(JSON.stringify([anchor.part, anchor.paragraph_id]));
    if (!paragraph) throw new Error("invalid_review");
    let location: ReviewItem["location"];
    let key = candidate.source_key ?? "", label = candidate.label;
    if (anchor.kind === "control") {
      const field = native.get(anchor.control_id);
      if (!field || field.value !== occurrence.value || doc.resolve(field.pos).before() !== paragraph.pos
        || decisions.get(candidate.id) === "dismissed")
        throw new Error("invalid_review");
      location = { kind: "control", id: field.id };
      key = field.key; label = field.label;
    } else {
      const { start, end } = anchor;
      if (decisions.get(candidate.id) === "accepted" || !Number.isInteger(start) || !Number.isInteger(end)
        || start < 0 || start > end || end > paragraph.chars.length)
        throw new Error("invalid_review");
      const from = paragraph.points[start]?.[0] ?? paragraph.pos + 1;
      const to = end === start ? from : paragraph.points[end - 1][1];
      if (paragraph.chars.slice(start, end).join("") !== occurrence.value || !allowedSpan(doc, from, to, occurrence.value))
        throw new Error("invalid_review");
      location = { kind: "span", from, to, text: occurrence.value };
    }
    return { id: candidate.id, occurrenceId: occurrence.id, reason: candidate.reason,
      sourceKey: candidate.source_key ?? null, context: candidate.context, label,
      key, type: "text", decision: location.kind === "control" ? "accepted" : decisions.get(candidate.id) ?? "proposed", missing: false, location };
  });
  return doc.type.create({ ...doc.attrs, review: { sourceVersion, items } }, doc.content, doc.marks);
}

function mappedReview(review: ReviewState, transaction: Transaction): ReviewState {
  const native = controls(transaction.doc);
  return { ...review, items: review.items.map(item => {
    if (item.location.kind === "control") {
      const field = native.get(item.location.id);
      return field ? { ...item, missing: false, label: field.label, key: field.key } : { ...item, missing: true };
    }
    if (item.missing) return item;
    const from = transaction.mapping.map(item.location.from, 1);
    const to = transaction.mapping.map(item.location.to, -1);
    return { ...item, missing: !allowedSpan(transaction.doc, from, to, item.location.text),
      location: { ...item.location, from, to } };
  }) };
}

export function reviewChanges(state: EditorState, transaction: Transaction): Transaction {
  const review = reviewState(state.doc);
  if (!transaction.docChanged || transaction.steps.some(step => {
    const json = step.toJSON();
    return json.stepType === "docAttr" && json.attr === "review";
  })) return transaction;
  // Undo/redo already carries the inverse review attribute step; never remap twice.
  const base = review ?? { sourceVersion: null, items: [...controls(state.doc).values()].map(field => localControl(field, "native_control")) };
  const mapped = mappedReview(base, transaction);
  const tracked = new Set(mapped.items.flatMap(item => item.location.kind === "control" ? [item.location.id] : []));
  for (const field of controls(transaction.doc).values()) if (!tracked.has(field.id)) mapped.items.push(localControl(field, "manual"));
  return mapped.items.length || review ? transaction.setDocAttribute("review", mapped) : transaction;
}

function localControl(field: FieldOccurrence, reason: "native_control" | "manual"): ReviewItem {
  return { id: `local:${field.id}`, occurrenceId: `local:${field.id}`, reason, sourceKey: field.key,
    context: [...field.value].slice(0, 1024).join(""), label: field.label, key: field.key,
    type: "text", decision: "accepted", missing: false, location: { kind: "control", id: field.id } };
}

export function reviewCandidate(state: EditorState, id: string, action: "dismiss" | "accept",
  options: { label?: string; key?: string; type?: string } = {}): Transaction | null {
  const review = reviewState(state.doc), item = review?.items.find(entry => entry.id === id);
  if (!review || !item || item.decision === "accepted") return null;
  if (action === "dismiss") return closeHistory(state.tr).setDocAttribute("review", {
    ...review, items: review.items.map(entry => entry.id === id ? { ...entry, decision: "dismissed" } : entry),
  });
  const label = options.label ?? item.label, identity = newFieldId();
  const key = options.key ?? (item.key || identity);
  if (item.missing || item.location.kind !== "span" || !validFieldProperty(label, 256)
    || !validFieldProperty(key, 512) || (options.type ?? "text") !== "text") return null;
  const { from, to, text } = item.location;
  if (!allowedSpan(state.doc, from, to, text)) return null;
  const node = state.schema.nodes.field.create({ id: identity, key, label }, state.doc.slice(from, to).content);
  const transaction = closeHistory(state.tr).replaceWith(from, to, node);
  const mapped = mappedReview(review, transaction);
  transaction.setDocAttribute("review", { ...mapped, items: mapped.items.map(entry => entry.id === id
    ? { ...entry, label, key, decision: "accepted", missing: false, location: { kind: "control", id: identity } } : entry) });
  return transaction.setSelection(TextSelection.create(transaction.doc, from + 1));
}

export function configureCandidate(state: EditorState, id: string, label: string, key: string, type = "text"): Transaction | null {
  const review = reviewState(state.doc), item = review?.items.find(entry => entry.id === id);
  if (!review || !item || item.missing || !validFieldProperty(label, 256) || !validFieldProperty(key, 512) || type !== "text") return null;
  const transaction = closeHistory(state.tr);
  if (item.location.kind === "control") {
    const field = controls(state.doc).get(item.location.id);
    if (!field) return null;
    transaction.setNodeMarkup(field.pos, undefined, { ...state.doc.nodeAt(field.pos)!.attrs, label, key });
  }
  return transaction.setDocAttribute("review", { ...review, items: review.items.map(entry => entry.id === id ? { ...entry, label, key } : entry) });
}

export function focusCandidate(state: EditorState, id: string): Transaction | null {
  const item = reviewState(state.doc)?.items.find(entry => entry.id === id);
  if (!item || item.missing) return null;
  const field = item.location.kind === "control" ? controls(state.doc).get(item.location.id) : null;
  const range = item.location.kind === "span" ? item.location : field ? { from: field.pos + 1, to: field.pos + field.size - 1 } : null;
  return range ? state.tr.setSelection(TextSelection.create(state.doc, range.from, range.to)).scrollIntoView() : null;
}
