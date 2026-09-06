import { act, fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { EditorState, TextSelection, NodeSelection } from "prosemirror-state";
import { history, undo, redo } from "prosemirror-history";
import { DOMParser, DOMSerializer } from "prosemirror-model";
import { editorSchema, fields } from "../src/editor/model";
import {
  createField,
  fieldTextInput,
  focusField,
  linkedChanges,
  updateField,
} from "../src/editor/transactions";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

const text = (value: string) => editorSchema.text(value);
const field = (id: string, value = "Ірина", key = "client") =>
  editorSchema.nodes.field.create(
    { id, key, label: "ПІБ" },
    value ? text(value) : [],
  );
function state(
  content = [text("Before "), field("a"), text(" after "), field("b")],
) {
  const paragraph = editorSchema.nodes.paragraph.create({ id: "p" }, content);
  const section = editorSchema.nodes.section.create(
    { part: "word/document.xml" },
    paragraph,
  );
  return EditorState.create({
    doc: editorSchema.nodes.doc.create(null, section),
    plugins: [history()],
  });
}

test("DOM parsing preserves source identities, styles and locked structures", () => {
  const original = editorSchema.nodeFromJSON(corpus);
  const container = document.createElement("div");
  const locked = editorSchema.nodes.lockedBlock.create({
    id: "unsupported",
    label: "Preserved object",
  });
  const withLocked = original.copy(
    original.content.replaceChild(
      0,
      original.firstChild!.copy(original.firstChild!.content.addToEnd(locked)),
    ),
  );
  container.append(
    DOMSerializer.fromSchema(editorSchema).serializeFragment(
      withLocked.content,
    ),
  );
  expect(DOMParser.fromSchema(editorSchema).parse(container).toJSON()).toEqual(
    withLocked.toJSON(),
  );
});

test("sidebar updates every explicit occurrence in one undoable operation, including empty values", () => {
  let current = state();
  const original = current.doc;
  current = current.apply(updateField(current, "client", "Їжак Ґанна"));
  expect(fields(current.doc).map((f) => f.value)).toEqual([
    "Їжак Ґанна",
    "Їжак Ґанна",
  ]);
  expect(
    undo(current, (tr) => {
      current = current.apply(tr);
    }),
  ).toBe(true);
  expect(current.doc.eq(original)).toBe(true);
  expect(
    redo(current, (tr) => {
      current = current.apply(tr);
    }),
  ).toBe(true);
  current = current.apply(updateField(current, "client", ""));
  expect(fields(current.doc).map((f) => f.value)).toEqual(["", ""]);
  current = current.apply(updateField(current, "client", "Ірина"));
  expect(fields(current.doc).map((f) => f.value)).toEqual(["Ірина", "Ірина"]);
  const transaction = updateField(current, "missing", "ignored");
  expect(transaction.doc.eq(current.doc)).toBe(true);
  expect(linkedChanges(current, transaction)).toBe(transaction);
});

test("direct changes synchronize linked controls and preserve ambiguous values for review", () => {
  const current = state();
  const [first, second] = fields(current.doc);
  const edited = current.tr.insertText(
    "Єва",
    first.pos + 1,
    first.pos + first.size - 1,
  );
  expect(
    fields(linkedChanges(current, edited).doc).map((f) => f.value),
  ).toEqual(["Єва", "Єва"]);
  const emptied = current.tr.delete(first.pos + 1, first.pos + first.size - 1);
  expect(
    fields(linkedChanges(current, emptied).doc).map((f) => f.value),
  ).toEqual(["", ""]);
  const ambiguous = current.tr
    .insertText("Б", second.pos + 1, second.pos + second.size - 1)
    .insertText("А", first.pos + 1, first.pos + first.size - 1);
  expect(
    fields(linkedChanges(current, ambiguous).doc).map((f) => f.value),
  ).toEqual(["А", "Б"]);
  expect(linkedChanges(current, current.tr).doc.eq(current.doc)).toBe(true);
});

test("native text input replaces selected field content without deleting its identity", () => {
  let current = state();
  const editor = {
    get state() {
      return current;
    },
    dispatch: (tr: typeof current.tr) => {
      current = current.apply(linkedChanges(current, tr));
    },
  };
  expect(fieldTextInput(editor, 2, 2, "normal")).toBe(false);
  current = current.apply(focusField(current, "a")!);
  expect(
    fieldTextInput(editor, current.selection.from, current.selection.to, "Єва"),
  ).toBe(true);
  expect(fields(current.doc).map((f) => [f.id, f.value])).toEqual([
    ["a", "Єва"],
    ["b", "Єва"],
  ]);
  const [first, second] = fields(current.doc);
  current = current.apply(
    current.tr.setSelection(
      TextSelection.create(current.doc, first.pos + 1, second.pos + 1),
    ),
  );
  expect(
    fieldTextInput(
      editor,
      current.selection.from,
      current.selection.to,
      "cross-field",
    ),
  ).toBe(false);
});

test("creates a field from mapped text selection, preserving styled split runs and navigation", () => {
  const mark = editorSchema.marks.source.create({
    id: "r",
    bold: true,
    italic: true,
    underline: true,
  });
  let current = state([text("Електронна "), text("пошта").mark([mark])]);
  current = current.apply(
    current.tr.setSelection(TextSelection.create(current.doc, 2, 18)),
  );
  const transaction = createField(current, "  Пошта  ", "new")!;
  current = current.apply(transaction);
  const created = fields(current.doc)[0];
  expect(created.label).toBe("Пошта");
  expect(created.value).toBe("Електронна пошта");
  expect(current.doc.nodeAt(created.pos + 12)?.marks[0].attrs.bold).toBe(true);
  const navigation = focusField(current, "new")!;
  expect(navigation.selection.from).toBe(created.pos + 1);
  expect(navigation.selection.to).toBe(created.pos + created.size - 1);
  expect(focusField(current, "missing")).toBeNull();
});

test("rejects empty, cross-paragraph, nested-control and locked selections", () => {
  let current = state();
  expect(createField(current, "x", "new")).toBeNull();
  const first = fields(current.doc)[0];
  current = current.apply(focusField(current, first.id)!);
  expect(createField(current, "x", "new")).toBeNull();
  current = current.apply(
    current.tr.setSelection(NodeSelection.create(current.doc, first.pos)),
  );
  expect(createField(current, "x", "new")).toBeNull();
  current = state([text("abc")]);
  current = current.apply(
    current.tr.setSelection(TextSelection.create(current.doc, 2, 4)),
  );
  expect(createField(current, " ", "new")).toBeNull();
  const end = current.doc.content.size - 1;
  current = current.apply(
    current.tr.insert(
      end,
      editorSchema.nodes.paragraph.create({ id: "p2" }, text("def")),
    ),
  );
  current = current.apply(
    current.tr.setSelection(TextSelection.create(current.doc, 2, end + 2)),
  );
  expect(createField(current, "x", "new")).toBeNull();
});

test("renders corpus controls, keeps the same editor and draft across locale changes, and cleans up", async () => {
  // jsdom has no layout engine; the real geometry path is verified in Playwright.
  Object.defineProperty(Range.prototype, "getClientRects", {
    configurable: true,
    value: () => [],
  });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", {
    configurable: true,
    value: () => new DOMRect(),
  });
  await setLanguage("uk");
  const { container, unmount } = render(
    <I18nextProvider i18n={i18n}>
      <DocumentEditor initialDocument={corpus} />
    </I18nextProvider>,
  );
  const editor = screen.getByRole("textbox", { name: "Редагований документ" });
  expect(container.querySelectorAll(".document-field")).toHaveLength(5);
  const inputs = screen
    .getAllByRole("textbox")
    .filter((el) => el.tagName === "INPUT");
  const input = inputs[1];
  fireEvent.change(input, { target: { value: "Ґанна Їжак" } });
  expect(container.querySelector(".document-field")).toHaveTextContent(
    "Ґанна Їжак",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Створити поле з виділення" }),
  );
  expect(screen.getByRole("alert")).toBeVisible();
  fireEvent.click(
    screen.getAllByRole("button", {
      name: "Перейти до поля: ПІБ клієнта",
    })[0],
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Скасувати" }),
  );
  expect(input).toHaveValue("[Введіть ПІБ клієнта]");
  fireEvent.click(
    screen.getByRole("button", { name: "Повторити" }),
  );
  expect(input).toHaveValue("Ґанна Їжак");
  await act(() => setLanguage("en"));
  expect(screen.getByRole("textbox", { name: "Editable document" })).toBe(
    editor,
  );
  expect(input).toHaveValue("Ґанна Їжак");
  unmount();
  expect(container.children).toHaveLength(0);
});
