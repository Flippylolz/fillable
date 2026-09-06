import { waitFor } from "@testing-library/react";
import { mountEditor, type EditorPresentation } from "../src/editor/adapter";
import { editorSchema, fields } from "../src/editor/model";
import { collapseFieldSelection, fieldLineBreak, fieldTextInput, retainComposedField } from "../src/editor/transactions";
import { EditorState, TextSelection } from "prosemirror-state";
import corpus from "../prototype/document.json";
import snapshot from "../prototype/fields.json";
import type { components } from "../generated/api";

beforeEach(() => {
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("composition maps bound review after DOM input and disposal cancels pending work", async () => {
  const host = document.createElement("div"); document.body.append(host);
  const updated = vi.fn(); let presentation: EditorPresentation;
  const editor = mountEditor(host, corpus, { onChange: vi.fn(), onUpdate: value => { presentation = value; updated(value); } });
  expect(editor.attachDiscovery(snapshot as components["schemas"]["FieldSnapshot"], snapshot.source_version_id)).toBe(true);
  const original = editor.exportSnapshot().document;
  const occurrences = presentation!.fields.filter(field => field.label === "ПІБ клієнта");
  editor.focusField(occurrences.at(-1)!.id);
  const dom = host.firstElementChild!;
  dom.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true }));
  expect(editor.exportSnapshot().composing).toBe(true);
  expect(editor.attachDiscovery(snapshot as components["schemas"]["FieldSnapshot"], snapshot.source_version_id)).toBe(false);
  const native = host.querySelector(`[data-field-id="${occurrences.at(-1)!.id}"]`)!;
  native.querySelector("[data-source-run]")!.textContent = "Ґанна Їжак";
  await waitFor(() => expect(presentation!.fields.find(field => field.id === occurrences.at(-1)!.id)!.value).toBe("Ґанна Їжак"));
  expect(presentation!.fields.find(field => field.id === occurrences[0].id)!.value).toBe(occurrences[0].value);
  dom.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }));
  await waitFor(() => expect(presentation!.fields.find(field => field.id === occurrences[0].id)!.value).toBe("Ґанна Їжак"));
  expect(editor.exportSnapshot().composing).toBe(false);
  expect(presentation!.review!.sourceVersion).toBe(snapshot.source_version_id);
  expect(presentation!.review!.items.filter(item => item.missing)).toHaveLength(0);
  expect(editor.undo()).toBe(true);
  expect(editor.exportSnapshot().document).toEqual(original);
  dom.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true }));
  dom.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }));
  const calls = updated.mock.calls.length;
  editor.destroy(); host.remove();
  await new Promise(resolve => setTimeout(resolve, 25));
  expect(updated).toHaveBeenCalledTimes(calls);
});

test("line-break commands apply only inside one field and active IME input stays native", () => {
  let state = EditorState.create({ doc: editorSchema.nodeFromJSON(corpus) });
  expect(fieldLineBreak(state)).toBe(false);
  const [first, second] = fields(state.doc);
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, first.pos + 1, first.pos + first.size - 1)));
  const dispatch = vi.fn();
  expect(fieldLineBreak(state)).toBe(true);
  expect(fieldLineBreak(state, dispatch)).toBe(true);
  expect(fields(dispatch.mock.calls[0][0].doc)[0].value).toBe("\n");
  expect(fieldTextInput({ state, dispatch, composing: true }, state.selection.from, state.selection.to, "候補")).toBe(false);
  expect(dispatch).toHaveBeenCalledTimes(1);
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, first.pos + 1, second.pos + 1)));
  expect(fieldLineBreak(state, dispatch)).toBe(false);
  expect(dispatch).toHaveBeenCalledTimes(1);
});


test("a native unwrapped control is retained only at its mapped editable range", () => {
  let source = EditorState.create({ doc: editorSchema.nodeFromJSON(corpus) });
  const first = fields(source.doc)[0];
  source = source.apply(source.tr.setSelection(TextSelection.create(source.doc, first.pos + 1, first.pos + first.size - 1)));
  const unwrapped = source.tr.replaceWith(first.pos, first.pos + first.size, source.schema.text("Єва"));
  const restored = retainComposedField(source, unwrapped, unwrapped.mapping);
  expect(fields(restored.doc).find(field => field.id === first.id)).toMatchObject({ value: "Єва", key: first.key, label: first.label });
  expect(fields(restored.doc)).toHaveLength(5);
  const retained = fields(restored.doc).find(field => field.id === first.id)!;
  expect(restored.doc.nodeAt(retained.pos + 1)!.marks).toEqual(source.doc.nodeAt(first.pos + 1)!.marks);
  const protectedEdit = source.tr.replaceWith(first.pos, first.pos + first.size, source.schema.nodes.lockedInline.create({ id: "locked", label: "Protected" }));
  const before = protectedEdit.doc;
  expect(retainComposedField(source, protectedEdit, protectedEdit.mapping).doc).toBe(before);
  const differentParagraph = source.tr.delete(first.pos, first.pos + first.size);
  const changed = differentParagraph.doc;
  expect(retainComposedField(source, differentParagraph, { map: pos => pos === first.pos ? 2 : changed.content.size - 2 }).doc).toBe(changed);
  expect(retainComposedField(EditorState.create({ doc: source.doc }), source.tr, source.tr.mapping).doc).toBe(source.doc);
});

test("arrow keys collapse a selected field before deletion without intercepting ordinary caret navigation", () => {
  let state = EditorState.create({ doc: editorSchema.nodeFromJSON(corpus) });
  expect(collapseFieldSelection(true)(state)).toBe(false);
  const first = fields(state.doc)[0];
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, first.pos + 1, first.pos + first.size - 1)));
  const dispatch = vi.fn();
  expect(collapseFieldSelection(true)(state)).toBe(true);
  expect(collapseFieldSelection(true)(state, dispatch)).toBe(true);
  expect(dispatch.mock.calls[0][0].selection.from).toBe(state.selection.to);
  expect(collapseFieldSelection(false)(state, dispatch)).toBe(true);
  expect(dispatch.mock.calls[1][0].selection.from).toBe(state.selection.from);
  state = state.apply(dispatch.mock.calls[1][0]);
  expect(collapseFieldSelection(false)(state, dispatch)).toBe(false);
});
