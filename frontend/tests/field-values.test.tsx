import { act, fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { RoundtripProof } from "../src/editor/RoundtripProof";
import { fieldValueIssue, FIELD_VALUE_LIMIT } from "../src/editor/fieldValues";
import { editorSchema, fields } from "../src/editor/model";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("field values use the server code-point limit and XML text character contract", () => {
  expect(fieldValueIssue("")).toBeNull();
  expect(fieldValueIssue("ҐЄІЇ іʼ’\n\t\r🙂\u0085\ue000\ufffd")).toBeNull();
  expect(fieldValueIssue("🙂".repeat(FIELD_VALUE_LIMIT))).toBeNull();
  expect(fieldValueIssue("🙂".repeat(FIELD_VALUE_LIMIT) + "Ї")).toBe("too_long");
  for (const invalid of ["\0", "\b", "\ufffe", "\uffff", "\ud800", "\udfff"])
    expect(fieldValueIssue(`before${invalid}after`)).toBe("invalid_text");
});

test("multiline values share editor state, invalid drafts survive locale changes and undo restores valid text", async () => {
  const changed = vi.fn(), validity = vi.fn();
  render(<I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} onDocumentChange={changed} onFieldValidityChange={validity} /></I18nextProvider>);
  const editor = screen.getByRole("textbox", { name: "Editable document" });
  const clients = screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" });
  const multiline = "Ґанна Їжак\nЄва\t🙂";
  fireEvent.change(clients[0], { target: { value: multiline } });
  expect(clients[1]).toHaveValue(multiline);
  expect(fields(editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]))[0].value).toBe(multiline);
  expect(validity).toHaveBeenLastCalledWith(true);
  const invalid = "Ї".repeat(FIELD_VALUE_LIMIT + 1);
  fireEvent.change(clients[1], { target: { value: invalid } });
  expect(clients[0]).toHaveValue(invalid);
  expect(clients[0]).toHaveAttribute("aria-invalid", "true");
  expect(clients[0]).toHaveAccessibleDescription(/65,536/);
  expect(validity).toHaveBeenLastCalledWith(false);
  const count = changed.mock.calls.length;
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  expect(screen.getAllByRole("textbox", { name: "Значення поля: ПІБ клієнта" })[0]).toBe(clients[0]);
  expect(clients[0]).toHaveValue(invalid);
  expect(clients[0]).toHaveAccessibleDescription(/залишається в чернетці/);
  expect(changed).toHaveBeenCalledTimes(count);
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));
  expect(clients[0]).toHaveValue(multiline);
  expect(clients[0]).not.toHaveAttribute("aria-invalid");
  expect(validity).toHaveBeenLastCalledWith(true);
  fireEvent.change(clients[0], { target: { value: "\ufffe" } });
  expect(clients[1]).toHaveValue("\ufffe");
  expect(clients[1]).toHaveAccessibleDescription(/DOCX не може зберегти/);
  fireEvent.change(clients[1], { target: { value: "" } });
  expect(clients[0]).toHaveValue("");
  expect(validity).toHaveBeenLastCalledWith(true);
});

test("the DOCX proof cannot export invalid field values and retains them until corrected", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ source: "fixture", digest: "revision", model: corpus }));
  vi.stubGlobal("fetch", fetcher);
  render(<I18nextProvider i18n={i18n}><RoundtripProof /></I18nextProvider>);
  const value = (await screen.findAllByRole("textbox", { name: "Field value: ПІБ клієнта" }))[0];
  fireEvent.change(value, { target: { value: "\ufffe" } });
  expect(screen.getByRole("button", { name: "Export DOCX" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Export DOCX" }));
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(value).toHaveValue("\ufffe");
  fireEvent.change(value, { target: { value: "Ґанна\nЇжак" } });
  expect(screen.getByRole("button", { name: "Export DOCX" })).toBeEnabled();
});
