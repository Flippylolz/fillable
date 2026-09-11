export const TITLE_CODE_POINT_LIMIT = 160;

/** The suggested copy name: template title plus the first filled field's value. */
export function defaultCopyTitle(templateTitle: string, values: string[]): string {
  const title = templateTitle.trim();
  const first = values.map(value => value.replace(/\s+/g, " ").trim()).find(value => value.length > 0);
  if (!first) return title;
  const composed = `${title} — ${first}`;
  const codePoints = Array.from(composed);
  return codePoints.length <= TITLE_CODE_POINT_LIMIT ? composed : codePoints.slice(0, TITLE_CODE_POINT_LIMIT).join("");
}
