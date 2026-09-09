import { calendarValid } from "./boxedDates";

// Mirrors the backend FieldType proposals; text stays the fallback for every
// value the detectors cannot confidently classify.
export type FieldType = "text" | "number" | "date";
export const FIELD_TYPES: readonly FieldType[] = ["text", "number", "date"];

export function isFieldType(value: unknown): value is FieldType {
  return value === "text" || value === "number" || value === "date";
}

// Optional minus, space-grouped thousands and one decimal separator, matching
// the backend proposal shape; commas stay untouched user data.
const NUMBER_VALUE =
  /^-(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?$|^\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?$|^\d+(?:[.,]\d+)?$/;

export function isValidNumberValue(value: string): boolean {
  return NUMBER_VALUE.test(value.trim());
}

/** Document text of a date field → ISO for the picker; null when unfilled/unparsable. */
export function parseDateValue(value: string): string | null {
  const text = value.trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  const dayFirst = /^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/.exec(text);
  const parts = iso ? [1, 2, 3].map(index => +iso[index])
    : dayFirst ? [+dayFirst[3], +dayFirst[2], +dayFirst[1]] : null;
  if (!parts) return null;
  const [year, month, day] = parts;
  if (!calendarValid(year, month, day)) return null;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** ISO picker value → canonical document format ДД.ММ.РРРР; null when invalid. */
export function formatDateValue(iso: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match || !calendarValid(+match[1], +match[2], +match[3])) return null;
  return `${match[3]}.${match[2]}.${match[1]}`;
}
