// Match the versioned field-schema limit, counting Unicode code points, not UTF-16 units.
export const FIELD_VALUE_LIMIT = 65536;
export type FieldValueIssue = "too_long" | "invalid_text" | null;

export function fieldValueIssue(value: string): FieldValueIssue {
  let count = 0;
  for (const character of value) {
    const code = character.codePointAt(0)!;
    if (!(code === 9 || code === 10 || code === 13 || (code >= 0x20 && code <= 0xd7ff)
      || (code >= 0xe000 && code <= 0xfffd) || code >= 0x10000)) return "invalid_text";
    if (++count > FIELD_VALUE_LIMIT) return "too_long";
  }
  return null;
}
