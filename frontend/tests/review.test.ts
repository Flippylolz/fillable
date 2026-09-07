import { EditorState, TextSelection } from "prosemirror-state";
import { history, undo, redo, closeHistory } from "prosemirror-history";
import type { Node as EditorNode } from "prosemirror-model";
import type { components } from "../generated/api";
import { editorSchema, fields } from "../src/editor/model";
import { linkedChanges, paragraphIdentities, removeField, updateField } from "../src/editor/transactions";
import { attachReview, configureCandidate, focusCandidate, reviewCandidate, reviewChanges, reviewState } from "../src/editor/review";
import corpus from "../prototype/document.json";
import generated from "../prototype/fields.json";

type Snapshot = components["schemas"]["FieldSnapshot"];
const snapshot = generated as Snapshot;
const version = snapshot.source_version_id;
const source = () => editorSchema.nodeFromJSON(corpus);
function editor(doc = attachReview(source(), snapshot, version)) {
  let state = EditorState.create({ doc, plugins: [history()] });
  return {
    get state() { return state; },
    dispatch(transaction: Parameters<typeof reviewChanges>[1] | null) {
      expect(transaction).not.toBeNull();
      state = state.apply(reviewChanges(state, paragraphIdentities(linkedChanges(state, transaction!))));
    },
  };
}
function small(content: EditorNode[], id = "p") {
  return editorSchema.nodes.doc.create(null, editorSchema.nodes.section.create({ part: "word/document.xml" },
    editorSchema.nodes.paragraph.create({ id }, content)));
}
function proposal(value: string, start: number, end: number): Snapshot {
  return { schema_version: 1, source_version_id: version, occurrences: [{ id: "o", value,
    anchor: { kind: "span", part: "word/document.xml", paragraph_id: "p", start, end } }],
    candidates: [{ id: "c", occurrence_id: "o", reason: "placeholder", label: "Імʼя", context: "context" }] };
}
const text = (value: string) => editorSchema.text(value);
const item = (doc: EditorNode, id: string) => reviewState(doc)!.items.find(candidate => candidate.id === id)!;

test("real detector proposals attach to exact corpus positions and native identities", () => {
  const doc = attachReview(source(), snapshot, version);
  const review = reviewState(doc)!;
  expect(review.items).toHaveLength(28);
  expect(review.items.filter(candidate => candidate.decision === "accepted")).toHaveLength(5);
  for (const candidate of review.items) {
    const state = EditorState.create({ doc });
    const focused = focusCandidate(state, candidate.id)!;
    const occurrence = snapshot.occurrences!.find(value => value.id === candidate.occurrenceId)!;
    expect(focused.doc.textBetween(focused.selection.from, focused.selection.to)).toBe(occurrence.value);
    expect(focused.docChanged).toBe(false);
  }
  const blank = review.items.find(candidate => candidate.reason === "blank_cell")!;
  const current = editor(doc);
  const before = current.state.doc;
  current.dispatch(reviewCandidate(current.state, blank.id, "accept"));
  expect(item(current.state.doc, blank.id).decision).toBe("accepted");
  expect(fields(current.state.doc)).toHaveLength(6);
  expect(fields(current.state.doc).some(field => field.value === "")).toBe(true);
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(current.state.doc.eq(before)).toBe(true);
  expect(redo(current.state, current.dispatch)).toBe(true);
  expect(item(current.state.doc, blank.id).decision).toBe("accepted");
});

test("Unicode split text after native node tokens maps to UTF-16 positions", () => {
  const control = editorSchema.nodes.field.create({ id: "native", key: "native", label: "Поле" }, text("😀Ї"));
  const doc = small([control, text(" \t😀 {{ІМ"), text("ʼЯ}}")]);
  const expected = proposal("{{ІМʼЯ}}", 6, 14);
  const attached = attachReview(doc, expected, version);
  const location = item(attached, "c").location;
  expect(location).toEqual({ kind: "span", from: 12, to: 20, text: "{{ІМʼЯ}}" });
  const current = editor(attached);
  current.dispatch(reviewCandidate(current.state, "c", "accept", { key: "native", label: "Інша мітка" }));
  expect(fields(current.state.doc).map(field => field.value)).toEqual(["😀Ї", "{{ІМʼЯ}}"]);
  expect(new Set(fields(current.state.doc).map(field => field.key))).toEqual(new Set(["native"]));
  expect(new Set(fields(current.state.doc).map(field => field.id)).size).toBe(2);
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(current.state.doc.eq(attached)).toBe(true);
});

test("surrounding edits move proposals; replacing them cannot redirect to equal text", () => {
  const current = editor(attachReview(small([text("before {{X}} after {{X}}")]), proposal("{{X}}", 7, 12), version));
  current.dispatch(closeHistory(current.state.tr).insertText("😀 ", 2));
  expect(item(current.state.doc, "c").location).toMatchObject({ from: 12, to: 17 });
  const moved = current.state.doc;
  current.dispatch(closeHistory(current.state.tr).delete(12, 17));
  expect(item(current.state.doc, "c").missing).toBe(true);
  expect(current.state.doc.textContent).toContain("{{X}}");
  expect(reviewCandidate(current.state, "c", "accept")).toBeNull();
  expect(focusCandidate(current.state, "c")).toBeNull();
  current.dispatch(current.state.tr.insertText("later ", 2));
  expect(item(current.state.doc, "c").missing).toBe(true);
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(item(current.state.doc, "c").missing).toBe(true);
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(current.state.doc.eq(moved)).toBe(true);
  expect(redo(current.state, current.dispatch)).toBe(true);
  expect(item(current.state.doc, "c").missing).toBe(true);
});

test("dismissal is content-neutral and undoable; acceptance retains source formatting", () => {
  const current = editor();
  const candidate = reviewState(current.state.doc)!.items.find(value => value.sourceKey === "ЕЛЕКТРОННА_ПОШТА" && value.location.kind === "span")!;
  const before = current.state.doc;
  current.dispatch(reviewCandidate(current.state, candidate.id, "dismiss"));
  expect(current.state.doc.content.eq(before.content)).toBe(true);
  expect(item(current.state.doc, candidate.id).decision).toBe("dismissed");
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(current.state.doc.eq(before)).toBe(true);
  const location = candidate.location;
  if (location.kind !== "span") throw new Error("expected span");
  const original = before.slice(location.from, location.to).content;
  current.dispatch(reviewCandidate(current.state, candidate.id, "accept"));
  const accepted = item(current.state.doc, candidate.id);
  expect(accepted.location.kind).toBe("control");
  const field = fields(current.state.doc).find(value => accepted.location.kind === "control" && value.id === accepted.location.id)!;
  expect(current.state.doc.nodeAt(field.pos)!.content.eq(original)).toBe(true);
  expect(reviewCandidate(current.state, candidate.id, "dismiss")).toBeNull();
});

test("configure labels and groups without changing values; deletion and undo retain identity", () => {
  const current = editor();
  const candidates = reviewState(current.state.doc)!.items.filter(value => value.location.kind === "control");
  const first = candidates[0], second = candidates[1];
  const originalValues = fields(current.state.doc).map(value => value.value);
  current.dispatch(configureCandidate(current.state, first.id, "Спільне імʼя", "group"));
  current.dispatch(configureCandidate(current.state, second.id, "Інше імʼя", "group"));
  expect(fields(current.state.doc).map(value => value.value)).toEqual(originalValues);
  expect(item(current.state.doc, first.id).key).toBe("group");
  expect(item(current.state.doc, second.id).key).toBe("group");
  current.dispatch(updateField(current.state, "group", "Ґанна"));
  expect(fields(current.state.doc).filter(value => value.key === "group").map(value => value.value)).toEqual(["Ґанна", "Ґанна"]);
  const before = current.state.doc;
  if (first.location.kind !== "control") throw new Error("expected control");
  current.dispatch(removeField(current.state, first.location.id));
  expect(item(current.state.doc, first.id).missing).toBe(true);
  expect(configureCandidate(current.state, first.id, "Label", "group")).toBeNull();
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(current.state.doc.eq(before)).toBe(true);
  expect(item(current.state.doc, first.id).missing).toBe(false);
  const focus = focusCandidate(current.state, first.id)!;
  expect(reviewChanges(current.state, focus)).toBe(focus);
});

test("proposal label and type validation is atomic and preserves drafts on rejection", () => {
  const current = editor(attachReview(small([text("{{X}}")]), proposal("{{X}}", 0, 5), version));
  for (const options of [{ label: " " }, { key: "" }, { label: "x".repeat(257) }, { key: "x".repeat(513) }, { key: "bad\n" }, { type: "date" }]) {
    expect(reviewCandidate(current.state, "c", "accept", options)).toBeNull();
    expect(configureCandidate(current.state, "c", options.label ?? "valid", options.key ?? "valid", options.type)).toBeNull();
  }
  expect(reviewCandidate(current.state, "unknown", "accept")).toBeNull();
  expect(configureCandidate(current.state, "unknown", "valid", "valid")).toBeNull();
  expect(focusCandidate(current.state, "unknown")).toBeNull();
  current.dispatch(configureCandidate(current.state, "c", "New label", "new key"));
  expect(item(current.state.doc, "c")).toMatchObject({ label: "New label", key: "new key", type: "text" });
  current.dispatch(reviewCandidate(current.state, "c", "dismiss"));
  current.dispatch(reviewCandidate(current.state, "c", "accept"));
  expect(fields(current.state.doc)[0]).toMatchObject({ label: "New label", key: "new key" });
});

test("wrong revision, stale anchors, duplicate identities and protected spans are rejected", () => {
  expect(() => attachReview(source(), snapshot, "wrong")).toThrow("invalid_review");
  expect(() => attachReview(source(), { ...snapshot, schema_version: 2 }, version)).toThrow();
  const doc = attachReview(source(), snapshot, version);
  expect(() => attachReview(doc, snapshot, version)).toThrow();
  const bad: Snapshot[] = [
    { ...snapshot, candidates: [snapshot.candidates![0], snapshot.candidates![0]] },
    { ...snapshot, occurrences: [...snapshot.occurrences!, snapshot.occurrences![0]] },
    { ...snapshot, occurrences: [] },
    { ...snapshot, candidates: Array.from({ length: 2001 }, (_, i) => ({ ...snapshot.candidates![0], id: String(i) })) },
  ];
  for (const value of bad) expect(() => attachReview(source(), value, version)).toThrow();
  const plain = small([text("{{X}}")]);
  for (const [start, end, value] of [[-1, 5, "{{X}}"], [0.5, 5, "{{X}}"], [0, 6, "{{X}}"], [4, 2, ""], [0, 5, "wrong"], [0, 0, ""]] as const)
    expect(() => attachReview(plain, proposal(value, start, end), version)).toThrow();
  expect(() => attachReview(small([text("{{X}}")], "other"), proposal("{{X}}", 0, 5), version)).toThrow();
  const locked = editorSchema.nodes.lockedInline.create({ id: "locked", label: "source" });
  expect(() => attachReview(small([locked, text("{{X}}")]), proposal("\ufffc{{X}}", 0, 6), version)).toThrow();
  const native = editorSchema.nodes.field.create({ id: "n", key: "n", label: "name" });
  expect(() => attachReview(small([text("{{"), native, text("X}}")]), proposal("{{X}}", 0, 5), version)).toThrow();
  const duplicate = plain.copy(plain.content.replaceChild(0, plain.firstChild!.copy(plain.firstChild!.content.append(plain.firstChild!.content))));
  expect(() => attachReview(duplicate, proposal("{{X}}", 0, 5), version)).toThrow();
});

test("no-review editor transactions remain unchanged", () => {
  const state = EditorState.create({ doc: source() });
  const transaction = state.tr.setSelection(TextSelection.create(state.doc, 2));
  expect(reviewChanges(state, transaction)).toBe(transaction);
  expect(focusCandidate(state, "missing")).toBeNull();
  expect(reviewCandidate(state, "missing", "dismiss")).toBeNull();
  expect(configureCandidate(state, "missing", "label", "key")).toBeNull();
});

test("undo restores distinct grouped values even when one already equals the new value", () => {
  const current = editor();
  const candidates = reviewState(current.state.doc)!.items.filter(value => value.location.kind === "control");
  current.dispatch(configureCandidate(current.state, candidates[0].id, "First", "shared"));
  current.dispatch(configureCandidate(current.state, candidates[1].id, "Second", "shared"));
  const before = current.state.doc;
  const values = fields(before).filter(value => value.key === "shared").map(value => value.value);
  expect(values[0]).not.toBe(values[1]);
  current.dispatch(updateField(current.state, "shared", values[0]));
  expect(undo(current.state, current.dispatch)).toBe(true);
  expect(current.state.doc.eq(before)).toBe(true);
  expect(redo(current.state, current.dispatch)).toBe(true);
  expect(fields(current.state.doc).filter(value => value.key === "shared").map(value => value.value)).toEqual([values[0], values[0]]);
});

test("native controls must match value, paragraph and unique identity", () => {
  for (const change of ["id", "value", "paragraph"]) {
    const bad = structuredClone(snapshot);
    const occurrence = bad.occurrences!.find(value => value.anchor.kind === "control")!;
    if (occurrence.anchor.kind !== "control") throw new Error("expected control");
    if (change === "id") occurrence.anchor.control_id = "unknown";
    if (change === "value") occurrence.value = "changed";
    if (change === "paragraph") occurrence.anchor.paragraph_id = bad.occurrences![0].anchor.paragraph_id;
    expect(() => attachReview(source(), bad, version)).toThrow("invalid_review");
  }
  const doc = source(), field = fields(doc)[0];
  const duplicated = EditorState.create({ doc }).tr.insert(field.pos, doc.nodeAt(field.pos)!).doc;
  expect(() => attachReview(duplicated, snapshot, version)).toThrow("invalid_review");
  expect(reviewState(attachReview(small([text("plain")]), { schema_version: 1, source_version_id: version }, version))!.items).toEqual([]);
});

test("actions revalidate live spans and reject missing or duplicate control identities", () => {
  const doc = attachReview(small([text("{{X}}")]), proposal("{{X}}", 0, 5), version);
  const stale = EditorState.create({ doc: EditorState.create({ doc }).tr.delete(2, 7).doc });
  expect(reviewCandidate(stale, "c", "accept")).toBeNull();
  const nativeDoc = attachReview(source(), snapshot, version);
  const candidate = reviewState(nativeDoc)!.items.find(value => value.location.kind === "control")!;
  if (candidate.location.kind !== "control") throw new Error("expected control");
  const identity = candidate.location.id;
  const field = fields(nativeDoc).find(value => value.id === identity)!;
  const state = EditorState.create({ doc: nativeDoc });
  const removed = EditorState.create({ doc: removeField(state, field.id)!.doc });
  expect(configureCandidate(removed, candidate.id, "name", "key")).toBeNull();
  expect(focusCandidate(removed, candidate.id)).toBeNull();
  const duplicated = EditorState.create({ doc: state.tr.insert(field.pos, nativeDoc.nodeAt(field.pos)!).doc });
  expect(configureCandidate(duplicated, candidate.id, "name", "key")).toBeNull();
  const updated = duplicated.apply(reviewChanges(duplicated, duplicated.tr.insertText("prefix ", 2)));
  expect(item(updated.doc, candidate.id).missing).toBe(true);
});

test("native review preserves an empty alias instead of adopting a discovery display label", () => {
  const control = editorSchema.nodes.field.create({ id: "native", key: "Стала група", label: "" }, text("Їжак"));
  const original = small([control]);
  const detected: Snapshot = { schema_version: 1, source_version_id: version,
    occurrences: [{ id: "native", value: "Їжак", anchor: { kind: "control", part: "word/document.xml", paragraph_id: "p", control_id: "native" } }],
    candidates: [{ id: "candidate", occurrence_id: "native", label: "Стала група", source_key: "Стала група", context: "Їжак", reason: "native_control" }],
    fields: [{ id: "group", type: "text", label: "Стала група", occurrence_ids: ["native"] }],
    decisions: [{ candidate_id: "candidate", status: "accepted", field_id: "group" }],
  };
  const reviewed = attachReview(original, detected, version);
  expect(reviewState(reviewed)!.items[0]).toMatchObject({ label: "", key: "Стала група", sourceKey: "Стала група", decision: "accepted" });
  expect(reviewed.content.eq(original.content)).toBe(true);
});
