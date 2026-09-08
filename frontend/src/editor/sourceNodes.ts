import type { Node } from "prosemirror-model";
import type { NodeView } from "prosemirror-view";
import type { SourcePresentation } from "./SourceLayout";

export function sourceNodeView(presentation: SourcePresentation | undefined) {
  return (node: Node): NodeView => {
    const dom = document.createElement(node.isInline ? "span" : "div");
    dom.contentEditable = "false"; dom.className = "document-unsupported";
    dom.dataset.locked = node.attrs.id;
    const data = (presentation?.locked as Record<string, {text?: string; shapes?: object[]}> | undefined)?.[node.attrs.id];
    dom.textContent = data?.text ?? node.attrs.label;
    for (const raw of data?.shapes ?? []) {
      const shape = raw as Record<string, unknown>;
      if (![shape.x, shape.y, shape.width, shape.height].every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 2000) || typeof shape.fill !== "string" || !/^#[0-9a-f]{6}$/i.test(shape.fill)) continue;
      const box = document.createElement("span");
      Object.assign(box.style, { position: "absolute", pointerEvents: "none", left: `${shape.x}pt`, top: `${shape.y}pt`, width: `${shape.width}pt`, height: `${shape.height}pt`, background: shape.fill, border: "0.5pt solid black", boxSizing: "border-box" });
      box.setAttribute("aria-hidden", "true"); dom.append(box);
    }
    return { dom, ignoreMutation: () => true };
  };
}
