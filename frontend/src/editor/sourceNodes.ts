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
      const inline = shape.placement === "inline";
      const extent = [shape.width, shape.height].every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 2000 && (v as number) > 0);
      const placed = inline || ([shape.x, shape.y].every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 2000));
      if (!extent || !placed || typeof shape.fill !== "string" || !(shape.fill === "transparent" || /^#[0-9a-f]{6}$/i.test(shape.fill))) continue;
      const box = document.createElement("span");
      const geometry = { boxSizing: "border-box", width: `${shape.width}pt`, height: `${shape.height}pt`, background: shape.fill, border: typeof shape.border === "string" && /^(?:none|(?:[0-9]|1[0-2])(?:\.\d+)?pt (?:solid|double|dotted|dashed) #[0-9a-f]{6})$/i.test(shape.border) ? shape.border : "0.5pt solid black" };
      // Inline shapes flow with text like Word's inline drawings; anchored ones keep
      // their source offsets relative to the paragraph box.
      Object.assign(box.style, inline ? { display: "inline-block", ...geometry } : { position: "absolute", pointerEvents: "none", left: `${shape.x}pt`, top: `${shape.y}pt`, ...geometry });
      box.setAttribute("aria-hidden", "true"); dom.append(box);
    }
    if (!dom.textContent && dom.querySelector("span[style]")) dom.classList.add("document-quiet");
    return { dom, ignoreMutation: () => true };
  };
}
