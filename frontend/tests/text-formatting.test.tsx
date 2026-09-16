import { DOMParser, DOMSerializer } from "prosemirror-model";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { EditorState, TextSelection } from "prosemirror-state";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { editorSchema, fields } from "../src/editor/model";
import { formatText } from "../src/editor/formatting";
import { setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("format commands preserve source marks, support partial selections and toggle existing overrides", () => {
  let state = EditorState.create({ doc: editorSchema.nodeFromJSON(corpus) });
  const field = fields(state.doc)[0];
  state = state.apply(state.tr.setSelection(TextSelection.create(state.doc, field.pos + 1, field.pos + field.size - 1)));
  const original = state.doc.nodeAt(field.pos + 1)!.marks[0];
  state = state.apply(formatText(state, "bold")!);
  const formatted = state.doc.nodeAt(field.pos + 1)!;
  expect(formatted.marks).toContainEqual(original);
  expect(formatted.marks.find(mark => mark.type.name === "format")!.attrs.bold).toBe(true);
  state = state.apply(formatText(state, "bold")!);
  expect(state.doc.nodeAt(field.pos + 1)!.marks[1].attrs.bold).toBe(false);
  expect(formatText(state, "italic", "missing")).toBeNull();
  const plain = editorSchema.nodeFromJSON({ type: "doc", content: [{ type: "section", content: [{ type: "paragraph", content: [{ type: "text", text: "Plain" }] }] }] });
  let bare = EditorState.create({ doc: plain });
  bare = bare.apply(bare.tr.setSelection(TextSelection.create(bare.doc, 2, 7)));
  expect(formatText(bare, "underline")!.doc.textContent).toBe("Plain");
});

test("fill formatting updates linked values and preview, undo restores styling and read-only blocks controls", async () => {
  vi.useFakeTimers();
  const changed = vi.fn();
  const modeChanged = vi.fn();
  const view = render(<DocumentEditor initialDocument={corpus} mode="fill" onModeChange={modeChanged} onDocumentChange={changed} />);
  const form = within(document.querySelector(".fill-form")! as HTMLElement);
  const entry = within(form.getAllByRole("article")[0]);
  for (const name of ["Bold", "Italic", "Underline"]) fireEvent.click(entry.getByRole("button", { name }));
  await act(async () => { vi.advanceTimersByTime(800); });
  const preview = document.querySelector(".fill-preview-content")!;
  expect(preview.querySelector('[data-text-format]')).not.toBeNull();
  expect(changed).toHaveBeenCalledTimes(3);
  fireEvent.click(entry.getByRole("button", { name: "Underline" }));
  fireEvent.click(entry.getByRole("button", { name: "Italic" }));
  fireEvent.click(entry.getByRole("button", { name: "Bold" }));
  fireEvent.click(form.getByRole("button", { name: "Undo" }));
  fireEvent.click(form.getByRole("button", { name: "Redo" }));
  fireEvent.click(entry.getByRole("button", { name: "Go to field: ПІБ клієнта" }));
  expect(modeChanged).toHaveBeenCalledWith("document");
  const tools = within(document.querySelector(".document-tools")! as HTMLElement);
  fireEvent.mouseDown(tools.getByRole("button", { name: "Bold" }));
  fireEvent.click(tools.getByRole("button", { name: "Bold" }));
  view.rerender(<DocumentEditor initialDocument={corpus} mode="fill" readOnly onDocumentChange={changed} />);
  expect(entry.getByRole("button", { name: "Bold" })).toBeDisabled();
  expect(screen.getAllByRole("button", { name: "Italic" }).every(button => (button as HTMLButtonElement).disabled)).toBe(true);
  vi.useRealTimers();
});

 test("formatting survives DOM edits with true, false and inherited properties", () => {
  for (const attrs of [{ bold: null, italic: null, underline: null }, { bold: true, italic: false, underline: null }, { bold: false, italic: true, underline: true }]) {
    const node = editorSchema.nodeFromJSON({ type: "doc", content: [{ type: "section", attrs: {part: "word/document.xml"}, content: [{type: "paragraph", content: [{ type: "text", text: "Ґ", marks: [{type: "format", attrs}] }] }] }] });
    const host = document.createElement("div");
    host.append(DOMSerializer.fromSchema(editorSchema).serializeFragment(node.content));
    const parsed = DOMParser.fromSchema(editorSchema).parse(host);
    expect(parsed.firstChild!.firstChild!.firstChild!.marks[0].attrs).toEqual(attrs);
  }
});
