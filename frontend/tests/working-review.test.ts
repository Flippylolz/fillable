import { readFileSync, writeFileSync } from "node:fs";
import { EditorState, TextSelection } from "prosemirror-state";
import { editorSchema, fields } from "../src/editor/model";
import { createField, linkedChanges, paragraphIdentities, removeField, updateField } from "../src/editor/transactions";
import { attachReview, reviewCandidate, reviewChanges, reviewState } from "../src/editor/review";
import type { components } from "../generated/api";
import corpus from "../prototype/document.json";
import proposals from "../prototype/fields.json";

test("persisted working fixture matches real editor transactions, including Unicode and missing origins", () => {
  vi.stubGlobal("crypto", { getRandomValues: (value: Uint8Array) => value.fill(17) });
  let state = EditorState.create({ doc: attachReview(editorSchema.nodeFromJSON(corpus), proposals as components["schemas"]["FieldSnapshot"], proposals.source_version_id) });
  const native = fields(state.doc)[0].id;
  function apply(transaction: typeof state.tr | null) {
    expect(transaction).not.toBeNull();
    state = state.apply(reviewChanges(state, paragraphIdentities(linkedChanges(state, transaction!))));
  }
  const accepted = reviewState(state.doc)!.items.find(item => item.reason === "placeholder")!;
  apply(reviewCandidate(state, accepted.id, "accept", { label: "Рецензент Їжак", key: "reviewer-fixture" }));
  apply(updateField(state, "reviewer-fixture", "Ґанна Їжак 🙂\nЄва\tІлля"));
  const dismissed = reviewState(state.doc)!.items.find(item => item.reason === "blank_line")!;
  apply(reviewCandidate(state, dismissed.id, "dismiss"));
  const removed = reviewState(state.doc)!.items.find(item => item.reason === "placeholder" && item.location.kind === "span")!;
  if (removed.location.kind !== "span") throw new Error("expected span");
  apply(state.tr.delete(removed.location.from, removed.location.to));
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, 2, 8)));
  apply(createField(state, "Заголовок Ґанни", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"));
  apply(removeField(state, native));
  apply(state.tr.insertText("🙂 ", 2));
  const actual = state.doc.toJSON();
  const path = "/fixtures/docx/v1/working-review.json";
  // Explicit local golden-generation mode; required CI only reads and compares.
  if (process.env.FILLABLE_WRITE_WORKING_FIXTURE === "1") writeFileSync(path, JSON.stringify(actual, null, 2) + "\n");
  expect(actual).toEqual(JSON.parse(readFileSync(path, "utf8")));
  expect(reviewState(state.doc)!.items.filter(item => item.missing)).toHaveLength(2);
  expect(reviewState(state.doc)!.items.find(item => item.id === accepted.id)).toMatchObject({ reason: "placeholder", decision: "accepted", location: { kind: "control" } });
  expect(reviewState(state.doc)!.items.some(item => item.reason === "manual" && !item.missing)).toBe(true);
  expect(fields(state.doc).find(field => field.key === "reviewer-fixture")!.value).toBe("Ґанна Їжак 🙂\nЄва\tІлля");
  expect(editorSchema.nodeFromJSON(actual).toJSON()).toEqual(actual);
});
