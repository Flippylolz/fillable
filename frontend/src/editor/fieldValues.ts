import { isValidNumberValue, parseDateValue, type FieldType } from "./fieldKinds";

// Match the versioned field-schema limit, counting Unicode code points, not UTF-16 units.
export const FIELD_VALUE_LIMIT = 65536;
export type FieldValueIssue = "too_long" | "invalid_text" | "invalid_number" | "invalid_date" | null;

export function fieldValueIssue(value: string, type: FieldType = "text"): FieldValueIssue {
  let count = 0;
  for (const character of value) {
    const code = character.codePointAt(0)!;
    if (!(code === 9 || code === 10 || code === 13 || (code >= 0x20 && code <= 0xd7ff)
      || (code >= 0xe000 && code <= 0xfffd) || code >= 0x10000)) return "invalid_text";
    if (++count > FIELD_VALUE_LIMIT) return "too_long";
  }
  // An empty value stays valid for every type: it means the field is unfilled.
  if (!value.trim()) return null;
  if (type === "number" && !isValidNumberValue(value)) return "invalid_number";
  if (type === "date" && !parseDateValue(value)) return "invalid_date";
  return null;
}
