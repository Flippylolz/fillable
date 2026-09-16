import { fireEvent, render, screen } from "@testing-library/react";
import { FieldInput } from "../src/editor/FieldInput";
import type { FieldSummary } from "../src/editor/adapter";

test.each(["text", "number", "date"] as const)("%s input stays mounted and focused across a temporary access check", type => {
  const field: FieldSummary = { id: "field", key: "key", label: "Name", type, value: type === "date" ? "16.09.2026" : "123", issue: null };
  const update = vi.fn();
  const view = render(<FieldInput field={field} readOnly={false} update={update} />);
  const input = screen.getByLabelText(/Name/) as HTMLInputElement;
  input.focus();
  if (type === "text") input.setSelectionRange(1, 2);
  view.rerender(<FieldInput field={field} readOnly update={update} />);
  expect(input).toHaveFocus();
  expect(input).not.toBeDisabled();
  expect(input).toHaveAttribute("readonly");
  view.rerender(<FieldInput field={field} readOnly={false} update={update} />);
  expect(screen.getByLabelText(/Name/)).toBe(input);
  expect(input).toHaveFocus();
  if (type === "text") expect([input.selectionStart, input.selectionEnd]).toEqual([1, 2]);
  fireEvent.change(input, { target: { value: type === "date" ? "2026-09-17" : "1234" } });
  expect(update).toHaveBeenCalledWith("key", type === "date" ? "17.09.2026" : "1234");
});
