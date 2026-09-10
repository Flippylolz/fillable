import type { Node } from "prosemirror-model";
import type { NodeView } from "prosemirror-view";
import { isLightFill, lineSnapDelta, type LineBox } from "./checkboxes";
import type { SourcePresentation } from "./SourceLayout";

/** Checkbox-sized rectangles may follow the reflowed label line, frames do not. */
const SNAP_LIMIT = 24;

/** Vertical bands of the paragraph's rendered text lines, one per wrapped row. */
function textLines(paragraph: Element): LineBox[] {
  const lines: LineBox[] = [];
  const range = document.createRange();
  const walker = document.createTreeWalker(paragraph, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    range.selectNodeContents(node);
    for (const rect of range.getClientRects()) {
      if (rect.width <= 0 || rect.height <= 0) continue;
      const line = lines.find(candidate => candidate.top < rect.bottom && rect.top < candidate.bottom);
      if (line) {
        line.top = Math.min(line.top, rect.top);
        line.bottom = Math.max(line.bottom, rect.bottom);
      } else {
        lines.push({ top: rect.top, bottom: rect.bottom });
      }
    }
  }
  return lines;
}

/**
 * Anchored offsets are measured against Word's line stacking; the editor wraps
 * and leads lines slightly differently, so checkbox-sized rectangles drift
 * below their labels. Once laid out, re-anchor such a box onto the text line
 * nearest the offset Word chose. Absent layout (tests, hidden views) is a no-op.
 */
function scheduleLineSnap(box: HTMLElement, anchoredTopPt: number): void {
  let attempts = 0;
  const measure = () => {
    const paragraph = box.closest("p");
    if (!paragraph || !box.isConnected || getComputedStyle(paragraph).position !== "relative") return;
    const rect = box.getBoundingClientRect();
    const lines = rect.height > 0 ? textLines(paragraph) : [];
    // The editor canvas may not be laid out yet on the first frame; wait for it.
    if (!lines.length) {
      if (++attempts < 60) requestAnimationFrame(measure);
      return;
    }
    const zoom = parseFloat(getComputedStyle(paragraph).zoom) || 1;
    const delta = lineSnapDelta(lines, rect.top, rect.height, zoom);
    if (delta) box.style.top = `${(anchoredTopPt * 4) / 3 + delta}px`;
  };
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(measure);
  else measure();
}

export function sourceNodeView(presentation: SourcePresentation | undefined, shapeLabel: () => string) {
  return (node: Node): NodeView => {
    const dom = document.createElement(node.isInline ? "span" : "div");
    dom.contentEditable = "false"; dom.className = "document-unsupported";
    dom.dataset.locked = node.attrs.id;
    const data = (presentation?.locked as Record<string, {text?: string; shapes?: object[]}> | undefined)?.[node.attrs.id];
    dom.textContent = data?.text ?? node.attrs.label;
    const overrides = (node.attrs.shapes ?? {}) as Record<string, string>;
    (data?.shapes ?? []).forEach((raw, index) => {
      const shape = raw as Record<string, unknown>;
      const inline = shape.placement === "inline";
      const extent = [shape.width, shape.height].every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 2000 && (v as number) > 0);
      const placed = inline || ([shape.x, shape.y].every(v => typeof v === "number" && Number.isFinite(v) && Math.abs(v) <= 2000));
      if (!extent || !placed || typeof shape.fill !== "string" || !(shape.fill === "transparent" || /^#[0-9a-f]{6}$/i.test(shape.fill))) return;
      const authored = shape.fill;
      const fill = overrides[String(index)] ?? authored;
      const togglable = fill !== "transparent";
      const box = document.createElement("span");
      const geometry = { boxSizing: "border-box", width: `${shape.width}pt`, height: `${shape.height}pt`, background: fill, border: typeof shape.border === "string" && /^(?:none|(?:[0-9]|1[0-2])(?:\.\d+)?pt (?:solid|double|dotted|dashed) #[0-9a-f]{6})$/i.test(shape.border) ? shape.border : "0.5pt solid black" };
      // Inline shapes flow with text like Word's inline drawings; anchored ones keep
      // their source offsets relative to the paragraph box. Togglable boxes stay
      // clickable above the paragraph's own text hit target.
      Object.assign(box.style, inline ? { display: "inline-block", ...geometry } : { position: "absolute", pointerEvents: togglable ? "auto" : "none", zIndex: togglable ? "1" : "auto", left: `${shape.x}pt`, top: `${shape.y}pt`, ...geometry });
      if (togglable) {
        box.className = "document-shape";
        box.dataset.index = String(index);
        box.dataset.fill = fill;
        box.setAttribute("role", "checkbox");
        box.setAttribute("aria-checked", isLightFill(fill) ? "false" : "true");
        const label = shapeLabel();
        if (label) box.setAttribute("aria-label", label);
      } else {
        box.setAttribute("aria-hidden", "true");
      }
      if (!inline && togglable && (shape.width as number) <= SNAP_LIMIT && (shape.height as number) <= SNAP_LIMIT)
        scheduleLineSnap(box, shape.y as number);
      dom.append(box);
    });
    if (!dom.textContent && dom.querySelector("span[style]")) dom.classList.add("document-quiet");
    return { dom, ignoreMutation: () => true };
  };
}
