import { EditorState, TextSelection } from "prosemirror-state";
import { closeHistory, history, undo, redo } from "prosemirror-history";
import { editorSchema, fields } from "../src/editor/model";
import { createField, focusField, manualFieldIssue, removeField } from "../src/editor/transactions";
import { reviewChanges, reviewState, type ReviewItem } from "../src/editor/review";
import { FIELD_RECORD_LIMIT } from "../src/editor/fieldProperties";

function state() {
  const marked = editorSchema.text("Їжак").mark([editorSchema.marks.source.create({ id: "source-run", bold: true })]);
  return EditorState.create({ doc: editorSchema.nodes.doc.create(null,
    editorSchema.nodes.section.create({ part: "word/document.xml" }, [
      editorSchema.nodes.paragraph.create({ id: "p1" }, marked),
      editorSchema.nodes.paragraph.create({ id: "p2" }, editorSchema.text("Далі ")),
    ])), plugins: [history()] });
}

test("manual fields retain source runs and one stable review record through movement, removal and history", () => {
  let current = state();
  const original = current.doc;
  const apply = (tr: typeof current.tr) => { current = current.apply(reviewChanges(current, tr)); };
  apply(current.tr.setSelection(TextSelection.create(current.doc, 2, 6)));
  const id = "a".repeat(32);
  apply(createField(current, "  Ручне поле  ", id)!);
  const record = reviewState(current.doc)!.items[0];
  expect(reviewState(current.doc)!.sourceVersion).toBeNull();
  expect(record).toMatchObject({ reason: "manual", label: "Ручне поле", decision: "accepted", missing: false, location: { kind: "control", id } });
  expect(fields(current.doc)[0]).toMatchObject({ id, key: id, value: "Їжак" });
  expect(current.doc.nodeAt(fields(current.doc)[0].pos + 1)!.marks[0].attrs.bold).toBe(true);
  expect(undo(current, apply)).toBe(true); expect(current.doc.eq(original)).toBe(true);
  expect(redo(current, apply)).toBe(true); expect(reviewState(current.doc)!.items).toEqual([record]);
  const before = fields(current.doc)[0], node = current.doc.nodeAt(before.pos)!;
  const move = closeHistory(current.tr).delete(before.pos, before.pos + before.size);
  move.insert(move.doc.content.size - 2, node); apply(move);
  expect(fields(current.doc)[0].pos).toBeGreaterThan(before.pos);
  expect(reviewState(current.doc)!.items).toEqual([record]);
  expect(focusField(current, id)!.selection.from).toBe(fields(current.doc)[0].pos + 1);
  apply(removeField(current, id)!);
  expect(current.doc.textContent).toContain("Їжак");
  expect(reviewState(current.doc)!.items[0]).toMatchObject({ id: record.id, missing: true });
  expect(undo(current, apply)).toBe(true);
  expect(reviewState(current.doc)!.items[0].missing).toBe(false);
  apply(closeHistory(current.tr).insert(current.doc.content.size - 2, node));
  expect(reviewState(current.doc)!.items).toHaveLength(1);
  expect(reviewState(current.doc)!.items[0].missing).toBe(true);
  expect(focusField(current, id)).toBeNull(); expect(removeField(current, id)).toBeNull();
});

test("invalid manual labels cannot alter selection or source text and the limit counts Unicode characters", () => {
  const initial = state();
  const current = initial.apply(initial.tr.setSelection(TextSelection.create(initial.doc, 2, 6)));
  const original = current.doc.toJSON(), selection = current.selection.toJSON();
  for (const label of [" ", "🙂".repeat(257), "bad\nlabel", "bad\u0085label", "\ufffe", "\ud800"]) {
    expect(manualFieldIssue(current, label)).toBe("invalid_label");
    expect(createField(current, label, "a".repeat(32))).toBeNull();
    expect(current.doc.toJSON()).toEqual(original); expect(current.selection.toJSON()).toEqual(selection);
  }
  const created = createField(current, "🙂".repeat(256), "a".repeat(32))!;
  expect(fields(created.doc)[0].label).toBe("🙂".repeat(256));
});

test("record capacity is explicit and edits without any fields do not invent review metadata", () => {
  let current = state();
  expect(reviewState(reviewChanges(current, current.tr.insertText("Before ", 2)).doc)).toBeNull();
  const field = (id: number) => editorSchema.nodes.field.create({ id: String(id), key: String(id), label: "Поле" });
  const crowded = current.tr.insert(2, Array.from({ length: FIELD_RECORD_LIMIT }, (_, id) => field(id)));
  expect(manualFieldIssue(current.apply(crowded), "Назва")).toBe("field_limit");
  const candidate: ReviewItem = { id: "c", occurrenceId: "o", reason: "placeholder", sourceKey: null, context: "Їжак", label: "Назва", key: "", type: "text", decision: "proposed", missing: false, location: { kind: "span", from: 2, to: 6, text: "Їжак" } };
  current = current.apply(current.tr.setDocAttribute("review", { sourceVersion: "source", items: Array.from({ length: FIELD_RECORD_LIMIT }, (_, id) => ({ ...candidate, id: `c${id}`, occurrenceId: `o${id}` })) }));
  expect(manualFieldIssue(current, "Назва")).toBe("field_limit");
});
