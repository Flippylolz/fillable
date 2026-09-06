import { fieldValueIssue } from "./fieldValues";

export const FIELD_LABEL_LIMIT = 256;
export const FIELD_RECORD_LIMIT = 2000;
export function validFieldProperty(value: string, limit: number): boolean {
  return typeof value === "string" && !!value.trim() && [...value].length <= limit
    && ![...value].some(character => {
      const code = character.codePointAt(0)!;
      return code < 32 || (code >= 127 && code <= 159);
    }) && fieldValueIssue(value) === null;
}
