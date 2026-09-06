import { act, fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import type { components } from "../generated/api";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { editorSchema } from "../src/editor/model";
import { attachReview, reviewState } from "../src/editor/review";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import generated from "../prototype/fields.json";

test("mounted editor tracks removed review controls and preserves history through locale changes", async () => {
  // jsdom has no layout; real selection/scroll geometry is covered in browsers.
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
  await setLanguage("en");
  const snapshot = generated as components["schemas"]["FieldSnapshot"];
  const doc = attachReview(editorSchema.nodeFromJSON(corpus), snapshot, snapshot.source_version_id);
  const changed = vi.fn();
  render(<I18nextProvider i18n={i18n}><DocumentEditor initialDocument={doc.toJSON()} onDocumentChange={changed} /></I18nextProvider>);
  const editor = await screen.findByRole("textbox", { name: "Editable document" });
  fireEvent.click(screen.getAllByRole("button", { name: "Remove field: ПІБ клієнта" })[0]);
  const latest = () => editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]);
  expect(reviewState(latest())!.items.filter(item => item.missing)).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(latest().eq(doc)).toBe(true);
  const count = changed.mock.calls.length;
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  expect(changed).toHaveBeenCalledTimes(count);
  fireEvent.click(screen.getByRole("button", { name: "Повторити" }));
  expect(reviewState(latest())!.items.filter(item => item.missing)).toHaveLength(1);
});
