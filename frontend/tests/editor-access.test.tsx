import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { mountEditor, type EditorPresentation } from "../src/editor/adapter";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import discovery from "../prototype/fields.json";
import type { components } from "../generated/api";

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("read-only adapter rejects every authored mutation but retains focus, draft and undo history", () => {
  const host = document.createElement("div"); document.body.append(host);
  let allowed = true, presentation: EditorPresentation;
  const editor = mountEditor(host, corpus, { canEdit: () => allowed, onChange: vi.fn(), onUpdate: value => { presentation = value; } });
  editor.attachDiscovery(discovery as components["schemas"]["FieldSnapshot"], discovery.source_version_id);
  const field = presentation!.fields[0];
  editor.updateField(field.key, "Чернетка Їжака");
  const draft = editor.exportSnapshot();
  allowed = false; // Simulates a deadline passing before a delayed UI timer.
  expect(editor.updateField(field.key, "Discard")).toBe(false);
  expect(editor.removeField(field.id)).toBe(false);
  expect(editor.createField("New")).toBe("read_only");
  expect(editor.undo()).toBe(false); expect(editor.redo()).toBe(false);
  const proposal = presentation!.review!.items.find(item => item.decision === "proposed")!;
  expect(editor.review(proposal.id, "dismiss", { label: proposal.label, key: proposal.key, type: "text" })).toBe(false);
  expect(editor.focusField(field.id)).toBe(true);
  const dom = host.firstElementChild!;
  fireEvent(dom, new InputEvent("beforeinput", { bubbles: true, cancelable: true, inputType: "insertText", data: "Blocked" }));
  fireEvent.keyDown(dom, { key: "Enter" });
  fireEvent(dom, new CompositionEvent("compositionstart", { bubbles: true }));
  expect(editor.exportSnapshot()).toEqual(draft);
  editor.refreshAccess(); expect(dom).toHaveAttribute("contenteditable", "false");
  allowed = true; editor.refreshAccess(); expect(editor.undo()).toBe(true);
  expect(editor.exportSnapshot().document).not.toEqual(draft.document);
  expect(editor.redo()).toBe(true); expect(editor.exportSnapshot().document).toEqual(draft.document);
  editor.destroy(); host.remove();
});

test("access loss during native composition settles the existing draft before becoming read-only", async () => {
  const host = document.createElement("div"); document.body.append(host);
  let allowed = true, presentation: EditorPresentation;
  const editor = mountEditor(host, corpus, { canEdit: () => allowed, onChange: vi.fn(), onUpdate: value => { presentation = value; } });
  const repeated = presentation!.fields.filter(field => field.label === "ПІБ клієнта");
  editor.focusField(repeated.at(-1)!.id);
  const dom = host.firstElementChild!;
  fireEvent(dom, new CompositionEvent("compositionstart", { bubbles: true }));
  allowed = false; editor.refreshAccess(); expect(dom).toHaveAttribute("contenteditable", "true");
  host.querySelector(`[data-field-id="${repeated.at(-1)!.id}"] [data-source-run]`)!.textContent = "Їжак зберігся";
  await waitFor(() => expect(presentation!.fields.find(field => field.id === repeated.at(-1)!.id)!.value).toBe("Їжак зберігся"));
  fireEvent(dom, new CompositionEvent("compositionend", { bubbles: true }));
  await waitFor(() => expect(editor.exportSnapshot().composing).toBe(false));
  expect(presentation!.fields.filter(field => field.key === repeated[0].key).every(field => field.value === "Їжак зберігся")).toBe(true);
  expect(dom).toHaveAttribute("contenteditable", "false");
  expect(editor.undo()).toBe(false);
  editor.destroy(); host.remove();
});

test("read-only React controls retain drafts while selection and review browsing remain available", async () => {
  const view = render(<I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} /></I18nextProvider>);
  const field = screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0];
  fireEvent.change(field, { target: { value: "Keep draft" } });
  await act(async () => view.rerender(<I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} readOnly /></I18nextProvider>));
  expect(field).toHaveValue("Keep draft"); expect(field).toBeDisabled();
  expect(screen.getByRole("button", { name: "Undo" })).toBeDisabled();
  expect(screen.getByRole("textbox", { name: "Editable document" })).toHaveAttribute("contenteditable", "false");
  expect(screen.getAllByRole("button", { name: "Go to field: ПІБ клієнта" })[0]).toBeEnabled();
});
