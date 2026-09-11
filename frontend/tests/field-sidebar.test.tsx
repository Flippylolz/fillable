import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import type { FieldSummary } from "../src/editor/adapter";
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
  const fields: FieldSummary[] = [{ id: "one", key: "shared", label: "ПІБ", value: "Ірина", type: "text", issue: null }, { id: "two", key: "shared", label: "ПІБ", value: "Єва", type: "text", issue: null }];
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

test("date fields render pickers writing canonical DD.MM.YYYY and number fields keep exact text", async () => {
  const update = vi.fn(), focus = vi.fn(), remove = vi.fn();
  const fields: FieldSummary[] = [
    { id: "d", key: "date", label: "Дата події", value: "7.3.2026", type: "date", issue: null },
    { id: "n", key: "sum", label: "Сума", value: "1 250,50", type: "number", issue: null },
  ];
  const ui = () => <I18nextProvider i18n={i18n}><FieldSidebar fields={fields} active="" focus={focus} update={update} remove={remove} /></I18nextProvider>;
  render(ui());
  expect(screen.getByText("Date")).toBeVisible();
  expect(screen.getByText("Number")).toBeVisible();
  const picker = screen.getByLabelText("Field value: Дата події") as HTMLInputElement;
  expect(picker).toHaveAttribute("type", "date");
  expect(picker).toHaveValue("2026-03-07");
  fireEvent.change(picker, { target: { value: "2026-12-31" } });
  expect(update).toHaveBeenLastCalledWith("date", "31.12.2026");
  fireEvent.change(picker, { target: { value: "" } });
  expect(update).toHaveBeenLastCalledWith("date", "");
  const amount = screen.getByLabelText("Field value: Сума");
  expect(amount).toHaveAttribute("inputmode", "decimal");
  expect(amount).toHaveValue("1 250,50");
  fireEvent.change(amount, { target: { value: "2 000,00" } });
  expect(update).toHaveBeenLastCalledWith("sum", "2 000,00");
});

test("unparsable dates and non-numeric amounts surface localized issues", async () => {
  const update = vi.fn(), focus = vi.fn(), remove = vi.fn();
  const fields: FieldSummary[] = [
    { id: "d", key: "date", label: "Дата", value: "31.02.2026", type: "date", issue: "invalid_date" },
    { id: "n", key: "sum", label: "Сума", value: "1 25O", type: "number", issue: "invalid_number" },
  ];
  const view = render(<I18nextProvider i18n={i18n}><FieldSidebar fields={fields} active="" focus={focus} update={update} remove={remove} /></I18nextProvider>);
  const alerts = screen.getAllByRole("alert");
  expect(alerts[0]).toHaveTextContent(/not a valid date in DD.MM.YYYY/i);
  expect(alerts[1]).toHaveTextContent(/not a number/i);
  await act(() => setLanguage("uk"));
  expect(screen.getAllByRole("alert").map(alert => alert.textContent)).toEqual([
    "Це значення не є коректною датою у форматі ДД.ММ.РРРР. Воно залишається в чернетці; виправте його перед експортом або збереженням.",
    "Це значення не є числом. Воно залишається в чернетці; виправте його перед експортом або збереженням.",
  ]);
  view.unmount();
});

test("compact cards size multiline inputs to their content and keep markers inline", async () => {
  const update = vi.fn(), focus = vi.fn(), remove = vi.fn();
  const fields: FieldSummary[] = [
    { id: "a", key: "a", label: "Адреса", value: "Однорядкове значення", type: "text", issue: null },
    { id: "b", key: "b", label: "Довіра", value: "рядок один\nрядок два\nрядок три", type: "text", issue: null },
  ];
  render(<I18nextProvider i18n={i18n}><FieldSidebar fields={fields} active="a" focus={focus} update={update} remove={remove} /></I18nextProvider>);
  const cards = screen.getAllByRole("article");
  expect(cards).toHaveLength(2);
  const header = cards[0].querySelector(".field-card-header")!;
  expect(header.querySelector(".field-type")!.textContent).toBe("Text");
  expect(header.querySelector(".field-active")!.textContent).toBe("Selected location");
  expect(header.querySelector(".field-type")!.tagName).toBe("SPAN");
  expect(within(cards[0]).getByRole("textbox")).toHaveAttribute("rows", "1");
  expect(within(cards[1]).getByRole("textbox")).toHaveAttribute("rows", "3");
  expect(within(cards[1]).getByRole("textbox")).not.toHaveAttribute("aria-current");
  const navigation = screen.getByRole("group", { name: "Field navigation" });
  expect(navigation.querySelector("p")).not.toBeNull();
  expect(within(navigation).getAllByRole("button")).toHaveLength(2);
  fireEvent.change(within(cards[0]).getByRole("textbox"), { target: { value: "Київ\nЦентр" } });
  expect(update).toHaveBeenCalledWith("a", "Київ\nЦентр");
});
