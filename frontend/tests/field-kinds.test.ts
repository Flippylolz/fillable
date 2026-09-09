import { formatDateValue, isFieldType, isValidNumberValue, parseDateValue } from "../src/editor/fieldKinds";
import { fieldValueIssue } from "../src/editor/fieldValues";

describe("field kinds", () => {
  test("numbers accept minus, space thousands and one decimal separator", () => {
    for (const value of ["42", "1 250,50", "1 250.50", "-1 250,50", "0,5", "2026", "1\u00a0250", "42 "])
      expect(isValidNumberValue(value)).toBe(true);
    for (const value of ["", "1 25O", "1.2.3", "12,", "1 25", "+42", "1 250,50 грн", "𐒠"])
      expect(isValidNumberValue(value)).toBe(false);
  });

  test("date values parse day-first and ISO forms and reject impossible calendars", () => {
    expect(parseDateValue("7.3.2026")).toBe("2026-03-07");
    expect(parseDateValue("07/12/2026")).toBe("2026-12-07");
    expect(parseDateValue("31-12-2026")).toBe("2026-12-31");
    expect(parseDateValue("2026-03-07")).toBe("2026-03-07");
    expect(parseDateValue("31.02.2026")).toBeNull();
    expect(parseDateValue("29.02.2026")).toBeNull();
    expect(parseDateValue("29.02.2028")).toBe("2028-02-29");
    expect(parseDateValue("")).toBeNull();
    expect(parseDateValue("16.09")).toBeNull();
    expect(parseDateValue("травень")).toBeNull();
    expect(formatDateValue("2026-03-07")).toBe("07.03.2026");
    expect(formatDateValue("2026-02-30")).toBeNull();
    expect(formatDateValue("07.03.2026")).toBeNull();
  });

  test("type guards and typed issues keep text values unrestricted", () => {
    expect(isFieldType("number") && isFieldType("date") && isFieldType("text")).toBe(true);
    expect(isFieldType("checkbox")).toBe(false);
    expect(fieldValueIssue("будь-який текст", "date")).toBe("invalid_date");
    expect(fieldValueIssue("  ", "number")).toBeNull();
    expect(fieldValueIssue("", "date")).toBeNull();
    expect(fieldValueIssue("abc", "number")).toBe("invalid_number");
    expect(fieldValueIssue("\ufffe", "number")).toBe("invalid_text");
  });
});
