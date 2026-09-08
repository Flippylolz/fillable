import { useId } from "react";

export type SourcePresentation = { [key: string]: object } | null;
const properties = new Set(["clear", "float", "display", "position", "font-variant", "text-transform", "font-family", "font-size", "font-weight", "font-style", "text-decoration", "color", "line-height", "margin-top", "margin-bottom", "margin-left", "margin-right", "text-indent", "text-align", "break-before", "border-collapse", "table-layout", "width", "height", "min-height", "vertical-align", "padding", "padding-top", "padding-bottom", "padding-left", "padding-right", "border", "border-top", "border-bottom", "border-left", "border-right", "box-sizing", "background", "margin"]);
function declarations(value: object) {
  return Object.entries(value).filter(([key, value]) => properties.has(key) && (key !== "position" || value === "relative") && (key !== "display" || value === "inline-table") && (key !== "float" || value === "left") && (key !== "clear" || value === "both") && typeof value === "string" && /^[\w\s.#"%-]+$/.test(value)).map(([key, value]) => `${key}:${value}!important`).join(";");
}
/** Presentation is deliberately outside the editor document and save payload. */
export function sourceRules(scope: string, presentation: SourcePresentation) {
  if (!presentation) return "";
  const prefix = `[data-layout=${JSON.stringify(scope)}]`;
  const section = declarations(presentation.section ?? {});
  const rules = [`${prefix} .ProseMirror{padding:0!important;background:transparent!important;box-shadow:none!important;overflow-wrap:normal!important}`, `${prefix} section[data-part="word/document.xml"]{${section}}`];
  for (const [id, styles] of Object.entries(presentation.nodes ?? {})) {
    if (!/^[\w/.:~-]+$/.test(id) || !styles || typeof styles !== "object") continue;
    rules.push(`${prefix} [data-source=${JSON.stringify(id)}],${prefix} [data-source-run=${JSON.stringify(id)}],${prefix} [data-source^=${JSON.stringify(`new:${id}:`)}]{${declarations(styles)}}`);
  }
  return rules.join("\n");
}
export function useSourceLayout(presentation: SourcePresentation | undefined) {
  const scope = useId();
  return { scope, rules: sourceRules(scope, presentation ?? null) };
}
