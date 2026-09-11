import { PAGE_BREAK_CLASS } from "../editor/pagination";

const PRINT_BASE = "@page{margin:15mm}body{margin:0;color:#000;background:#fff}.document-canvas{padding:0!important;background:#fff!important}.document-canvas .ProseMirror{min-height:0!important;box-shadow:none!important;zoom:1!important}";

/**
 * Renders a detached clone of the editor canvas alone into a hidden frame and
 * invokes the browser print dialog for exactly that view. Returns false when
 * in-page printing is unavailable or fails, so the UI can suggest a local save.
 */
export function printDocumentNode(node: Element | null | undefined, layout: { rules: string; scope: string }): boolean {
  if (!node) return false;
  const clone = node.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(`.${PAGE_BREAK_CLASS}`).forEach(marker => marker.remove());
  const frame = document.createElement("iframe");
  frame.className = "print-frame";
  frame.setAttribute("aria-hidden", "true");
  document.body.appendChild(frame);
  const win = frame.contentWindow, doc = frame.contentDocument;
  if (!win || !doc) { frame.remove(); return false; }
  const cleanup = () => frame.remove();
  if (typeof win.addEventListener === "function") win.addEventListener("afterprint", cleanup, { once: true });
  setTimeout(cleanup, 60000);
  try {
    doc.open();
    doc.write(`<!doctype html><html><head><meta charset="utf-8"><style>${layout.rules}</style><style>${PRINT_BASE}</style></head>`
      + `<body data-layout=${JSON.stringify(layout.scope)}><div class="document-canvas" data-layout=${JSON.stringify(layout.scope)}>${clone.outerHTML}</div></body></html>`);
    doc.close();
    win.focus();
    win.print();
    return true;
  } catch {
    cleanup();
    return false;
  }
}
