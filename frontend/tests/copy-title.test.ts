import { defaultCopyTitle, TITLE_CODE_POINT_LIMIT } from "../src/workspace/copyTitle";

test("the default copy title is the template title when no field has a value", () => {
  expect(defaultCopyTitle("Довідка ТБ-09", [])).toBe("Довідка ТБ-09");
  expect(defaultCopyTitle("Довідка ТБ-09", ["", "   ", "\n\t"])).toBe("Довідка ТБ-09");
});

test("the first filled field value in document order is appended after an em dash", () => {
  expect(defaultCopyTitle("Довідка", ["", "  Єва Ковальчук  "])).toBe("Довідка — Єва Ковальчук");
  expect(defaultCopyTitle("Довідка", ["", "\tІван\nПетренко\t"])).toBe("Довідка — Іван Петренко");
});

test("internal whitespace collapses and the suggestion respects the title code point limit", () => {
  const result = defaultCopyTitle("T", [`  ${"Ґ".repeat(TITLE_CODE_POINT_LIMIT)}  `]);
  expect(Array.from(result).length).toBe(TITLE_CODE_POINT_LIMIT);
  expect(result.startsWith("T — ҐҐ")).toBe(true);
  const astral = defaultCopyTitle("Довідка", ["🙂".repeat(200)]);
  expect(Array.from(astral).length).toBe(TITLE_CODE_POINT_LIMIT);
  expect(astral.endsWith("🙂")).toBe(true);
});
