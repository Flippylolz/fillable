import { fireEvent, render, screen } from "@testing-library/react";
import { FillForm } from "../src/editor/FillForm";
import { setLanguage } from "../src/i18n";
import type { FieldSummary } from "../src/editor/adapter";

beforeEach(async () => { await setLanguage("en"); });

function setup(readOnly = false) {
  const fields: FieldSummary[] = ["text", "number", "date"].map((type, index) => ({
    id: String(index), key: String(index), label: type, type: type as FieldSummary["type"],
    value: type === "date" ? "28.09.2026" : "123", issue: null,
  }));
  const update = vi.fn();
  render(<FillForm fields={fields} active="" update={update} focus={vi.fn()} remove={vi.fn()}
    readOnly={readOnly} undo={vi.fn()} redo={vi.fn()} canUndo canRedo format={vi.fn()} />);
  return { update, inputs: fields.map(field => screen.getByLabelText(`Field value: ${field.label}`)) };
}

test.each([false, true])("Tab traverses mixed fill inputs in both directions during readOnly=%s", readOnly => {
  const { inputs, update } = setup(readOnly);
  inputs[0].focus();
  expect(fireEvent.keyDown(inputs[0], { key: "Tab" })).toBe(false);
  expect(inputs[1]).toHaveFocus();
  expect(fireEvent.keyDown(inputs[1], { key: "Tab" })).toBe(false);
  expect(inputs[2]).toHaveFocus();
  expect(fireEvent.keyDown(inputs[2], { key: "Tab", shiftKey: true })).toBe(false);
  expect(inputs[1]).toHaveFocus();
  expect(fireEvent.keyDown(inputs[1], { key: "Tab", shiftKey: true })).toBe(false);
  expect(inputs[0]).toHaveFocus();
  expect(update).not.toHaveBeenCalled();
});

test("boundary tabs and field action buttons retain native keyboard navigation", () => {
  const { inputs } = setup();
  expect(fireEvent.keyDown(inputs[0], { key: "Tab", shiftKey: true })).toBe(true);
  expect(fireEvent.keyDown(inputs[2], { key: "Tab" })).toBe(true);
  expect(fireEvent.keyDown(screen.getByRole("button", { name: "Go to field: text" }), { key: "Tab" })).toBe(true);
});

test.each([
  { key: "Enter" }, { key: "Tab", altKey: true }, { key: "Tab", ctrlKey: true },
  { key: "Tab", metaKey: true }, { key: "Tab", isComposing: true },
])("ordinary editing and modified Tab stay native: %j", event => {
  const { inputs } = setup(); inputs[0].focus();
  expect(fireEvent.keyDown(inputs[0], event)).toBe(true);
  expect(inputs[0]).toHaveFocus();
});
