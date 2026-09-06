import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { FieldSidebar } from "../src/editor/FieldSidebar";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("occurrence navigation distinguishes repeated controls, preserves locale/selection and does not dirty content", async () => {
  const changed = vi.fn();
  render(<I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} onDocumentChange={changed} /></I18nextProvider>);
  const editor = await screen.findByRole("textbox", { name: "Editable document" });
  fireEvent.click(screen.getByRole("button", { name: "Next field" }));
  expect(screen.getByRole("article", { name: "Field location 1: ПІБ клієнта" })).toHaveAttribute("aria-current", "true");
  expect(screen.getByRole("button", { name: "Previous field" })).toBeDisabled();
  expect(editor).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Next field" }));
  expect(screen.getByText("Location 2 of 5")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Previous field" }));
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  expect(screen.getByText("Розташування 1 з 5")).toBeVisible();
  for (let index = 0; index < 4; index++) fireEvent.click(screen.getByRole("button", { name: "Наступне поле" }));
  const last = screen.getByRole("article", { name: "Розташування поля 5: ПІБ клієнта" });
  expect(last).toHaveAttribute("aria-current", "true");
  expect(screen.getByRole("article", { name: "Розташування поля 1: ПІБ клієнта" })).not.toHaveAttribute("aria-current");
  expect(screen.getByRole("button", { name: "Наступне поле" })).toBeDisabled();
  expect(changed).not.toHaveBeenCalled();
  fireEvent.click(within(last).getByRole("button", { name: "Прибрати поле: ПІБ клієнта" }));
  expect(last).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));
  expect(screen.getByRole("article", { name: "Розташування поля 5: ПІБ клієнта" })).toBeVisible();
});

test("unselected navigation has explicit endpoints, conflict values remain visible and an empty sidebar explains field creation", async () => {
  const focus = vi.fn(), update = vi.fn(), remove = vi.fn();
  const fields = [{ id: "one", key: "shared", label: "ПІБ", value: "Ірина", issue: null }, { id: "two", key: "shared", label: "ПІБ", value: "Єва", issue: null }];
  const ui = (empty = false) => <I18nextProvider i18n={i18n}><FieldSidebar fields={empty ? [] : fields} active="" focus={focus} update={update} remove={remove} /></I18nextProvider>;
  const view = render(ui());
  expect(screen.getAllByText("Linked occurrences have different values. Review them before editing.")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Previous field" })); expect(focus).toHaveBeenLastCalledWith("two");
  fireEvent.click(screen.getByRole("button", { name: "Next field" })); expect(focus).toHaveBeenLastCalledWith("one");
  const second = within(screen.getByRole("article", { name: "Field location 2: ПІБ" }));
  expect(second.getByRole("textbox")).toHaveValue("Єва");
  fireEvent.change(second.getByRole("textbox"), { target: { value: "Ґанна" } }); expect(update).toHaveBeenCalledWith("shared", "Ґанна");
  view.rerender(ui(true));
  expect(screen.getByText("No fields yet. Select text in the document to create a field, or review the suggestions.")).toBeVisible();
  expect(screen.queryByRole("button")).toBeNull();
  await act(() => setLanguage("uk"));
  expect(screen.getByText(/Полів ще немає/)).toBeVisible();
});
