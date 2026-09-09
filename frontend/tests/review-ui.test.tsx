import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import type { components } from "../generated/api";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { editorSchema, fields } from "../src/editor/model";
import { reviewState } from "../src/editor/review";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import generated from "../prototype/fields.json";

const snapshot = generated as components["schemas"]["FieldSnapshot"];
beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});
function ui(changed = vi.fn(), discovery: typeof snapshot | null = snapshot, reopen?: () => void) {
  return <I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} discoverySnapshot={discovery}
    sourceVersion={snapshot.source_version_id} onDocumentChange={changed} onReopen={reopen} /></I18nextProvider>;
}
async function openReview() { fireEvent.click(await screen.findByText("Review fields")); }

test("initial proposals do not dirty the document; review validates drafts and accepts through undoable operations", async () => {
  const changed = vi.fn(); render(ui(changed)); await openReview();
  expect(changed).not.toHaveBeenCalled();
  expect(screen.getAllByRole("article", { name: /^Field suggestion:/ })).toHaveLength(10);
  const first = screen.getAllByRole("article", { name: /^Field suggestion:/ })[0], card = within(first);
  const originalLabel = card.getByLabelText("Field label").getAttribute("value");
  fireEvent.change(card.getByLabelText("Field label"), { target: { value: "" } });
  fireEvent.click(card.getByRole("button", { name: "Accept" }));
  expect(card.getByRole("alert")).toBeVisible(); expect(changed).not.toHaveBeenCalled();
  expect(card.getByLabelText("Field label")).toHaveAttribute("aria-invalid", "true");
  expect(card.getByLabelText("Field label")).toHaveAccessibleDescription(card.getByRole("alert").textContent!);
  fireEvent.change(card.getByLabelText("Field label"), { target: { value: "Reviewed name" } });
  fireEvent.change(card.getByLabelText("Link values with"), { target: { value: "" } });
  fireEvent.click(card.getByRole("button", { name: "Apply settings" }));
  expect(card.getByLabelText("Field label")).not.toHaveAttribute("aria-invalid");
  const latest = () => editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]);
  expect(latest().content.eq(editorSchema.nodeFromJSON(corpus).content)).toBe(true);
  fireEvent.click(card.getByRole("button", { name: "Go to location" }));
  expect(screen.getByRole("textbox", { name: "Editable document" })).toHaveFocus();
  const count = changed.mock.calls.length;
  fireEvent.click(card.getByRole("button", { name: "Accept" }));
  expect(changed).toHaveBeenCalledTimes(count + 1);
  expect(fields(latest())).toHaveLength(6);
  expect(await screen.findByRole("textbox", { name: "Field value: Reviewed name" })).toHaveValue("{{ІМʼЯ_РЕЦЕНЗЕНТА}}");
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(fields(latest())).toHaveLength(5);
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(within(screen.getAllByRole("article", { name: /^Field suggestion:/ })[0]).getByLabelText("Field label")).toHaveValue(originalLabel);
});

test("pagination, dismissals and filters keep content intact and clamp a shrinking last page", async () => {
  const changed = vi.fn(); render(ui(changed)); await openReview();
  fireEvent.change(screen.getByLabelText("Show"), { target: { value: "dismissed" } });
  expect(screen.getByText("No fields in this view.")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Show"), { target: { value: "proposed" } });
  expect(screen.getByRole("button", { name: "Previous suggestions" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Next suggestions" }));
  fireEvent.click(screen.getByRole("button", { name: "Next suggestions" }));
  expect(screen.getByRole("button", { name: "Next suggestions" })).toBeDisabled();
  expect(screen.getAllByRole("article", { name: /^Field suggestion:/ })).toHaveLength(3);
  for (let index = 0; index < 3; index++) fireEvent.click(within(screen.getAllByRole("article", { name: /^Field suggestion:/ })[0]).getByRole("button", { name: "Dismiss" }));
  expect(screen.getByText("2 of 2")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Previous suggestions" }));
  expect(screen.getByText("1 of 2")).toBeVisible();
  const latest = editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]);
  expect(latest.content.eq(editorSchema.nodeFromJSON(corpus).content)).toBe(true);
  fireEvent.change(screen.getByLabelText("Show"), { target: { value: "dismissed" } });
  expect(screen.getAllByRole("article", { name: /^Field suggestion:/ })).toHaveLength(3);
  fireEvent.click(within(screen.getAllByRole("article", { name: /^Field suggestion:/ })[0]).getByRole("button", { name: "Accept" }));
  expect(screen.getAllByRole("article", { name: /^Field suggestion:/ })).toHaveLength(2);
});

test("native configuration preserves values, missing locations are explicit and locale keeps input drafts", async () => {
  const changed = vi.fn(); const view = render(ui(changed)); await openReview();
  fireEvent.change(screen.getByLabelText("Show"), { target: { value: "accepted" } });
  const first = screen.getAllByRole("article", { name: /^Field suggestion:/ })[0], card = within(first);
  fireEvent.change(card.getByLabelText("Field label"), { target: { value: "Native label" } });
  const group = card.getByLabelText("Link values with") as HTMLSelectElement;
  const another = [...group.options].find(option => option.value && option.value !== group.value)!;
  fireEvent.change(group, { target: { value: another.value } });
  fireEvent.click(card.getByRole("button", { name: "Apply settings" }));
  const latest = () => editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]);
  expect(fields(latest()).map(field => field.value)).toEqual(fields(editorSchema.nodeFromJSON(corpus)).map(field => field.value));
  fireEvent.change(card.getByLabelText("Field label"), { target: { value: "Чернетка назви" } });
  const editor = screen.getByRole("textbox", { name: "Editable document" });
  const count = changed.mock.calls.length;
  await act(() => setLanguage("uk"));
  expect(card.getByLabelText("Назва поля")).toHaveValue("Чернетка назви");
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  expect(changed).toHaveBeenCalledTimes(count);
  view.rerender(ui(changed, structuredClone(snapshot)));
  expect(card.getByLabelText("Назва поля")).toHaveValue("Чернетка назви");
  fireEvent.click(screen.getByRole("button", { name: "Прибрати поле: Native label" }));
  expect(reviewState(latest())!.items.filter(item => item.missing)).toHaveLength(1);
  expect(card.getByRole("button", { name: "Перейти до місця" })).toBeDisabled();
  expect(card.getByRole("status")).toHaveTextContent("видалено або змінено");
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));
  expect(card.getByRole("button", { name: "Перейти до місця" })).toBeEnabled();
});

test("late proposals cannot replace an edited draft and reopening requires an explicit action", async () => {
  const changed = vi.fn(), reopen = vi.fn(); const view = render(ui(changed, null, reopen));
  const value = (await screen.findAllByRole("textbox", { name: "Field value: ПІБ клієнта" }))[0];
  fireEvent.change(value, { target: { value: "My draft" } });
  const count = changed.mock.calls.length;
  view.rerender(ui(changed, snapshot, reopen));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your draft has changed");
  expect(value).toHaveValue("My draft"); expect(changed).toHaveBeenCalledTimes(count);
  const local = reviewState(editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]))!;
  expect(local.sourceVersion).toBeNull();
  expect(local.items).toHaveLength(5);
  expect(local.items.every(item => item.decision === "accepted")).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Reopen saved document" }));
  expect(reopen).toHaveBeenCalledOnce();
});

test("the field type dropdown applies reviewable kinds and retypes the sidebar input", async () => {
  const changed = vi.fn(); render(ui(changed)); await openReview();
  const first = screen.getAllByRole("article", { name: /^Field suggestion:/ })[0], card = within(first);
  const type = card.getByLabelText("Field type");
  expect(type).toBeEnabled();
  fireEvent.change(type, { target: { value: "date" } });
  fireEvent.click(card.getByRole("button", { name: "Apply settings" }));
  const latest = () => editorSchema.nodeFromJSON(changed.mock.calls.at(-1)![0]);
  expect(reviewState(latest())!.items[0].type).toBe("date");
  expect(latest().content.eq(editorSchema.nodeFromJSON(corpus).content)).toBe(true);
  fireEvent.click(card.getByRole("button", { name: "Accept" }));
  const value = await screen.findByLabelText("Field value: ІМʼЯ_РЕЦЕНЗЕНТА");
  expect(value).toHaveAttribute("type", "date");
  expect(within(value.closest("article")!).getByText("Date")).toBeVisible();
});
