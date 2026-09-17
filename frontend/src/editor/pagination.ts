import type { Node as EditorNode } from "prosemirror-model";
import { Plugin, PluginKey } from "prosemirror-state";
import { Decoration, DecorationSet, type EditorView } from "prosemirror-view";

export const PAGE_BREAK_CLASS = "document-page-break";
const BODY_PART = "word/document.xml";

/** Top-level block start offset in unzoomed page pixels, from the content-box top. */
export type BlockFlow = { top: number; bottom: number; forced: boolean };
/** Editor position of a block that begins a new page, and that page's number. */
export type PageBreakSpec = { pos: number; page: number };

/**
 * Honor explicit source breaks and move blocks that overflow the content height
 * onto the next page. Approximate by design: breaks fall on block boundaries, never
 * inside one, and Word's exact pagination is not reproduced.
 */
export function pageStarts(blocks: BlockFlow[], contentHeight: number): number[] {
  const starts: number[] = [];
  let pageTop = 0;
  for (let index = 1; index < blocks.length; index += 1) {
    const top = blocks[index].top;
    if (blocks[index].forced || blocks[index].bottom - pageTop > contentHeight) {
      starts.push(index);
      pageTop = top;
    }
  }
  return starts;
}

function scale(dom: HTMLElement): number {
  const zoom = parseFloat((getComputedStyle(dom) as CSSStyleDeclaration & { zoom: string }).zoom);
  return Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
}

function geometry(dom: HTMLElement): {
  section: HTMLElement;
  contentHeight: number;
  contentTop: number;
  scale: number;
} | null {
  const section = dom.querySelector(`:scope > section[data-part="${BODY_PART}"]`);
  if (!(section instanceof HTMLElement)) return null;
  const style = getComputedStyle(section);
  const pageHeight = parseFloat(style.minHeight);
  const contentTop = parseFloat(style.paddingTop);
  const contentHeight = pageHeight - contentTop - parseFloat(style.paddingBottom);
  if (!Number.isFinite(contentHeight) || contentHeight <= 0) return null;
  return { section, contentHeight, contentTop, scale: scale(dom) };
}

/** Shared measurement for the live editor and the visible fill clone. */
export function measurePageStarts(dom: HTMLElement): number[] {
  const layout = geometry(dom);
  if (!layout) return [];
  const { section, contentHeight, contentTop, scale: zoom } = layout;
  const sectionTop = section.getBoundingClientRect().top;
  const flows: BlockFlow[] = [];
  let spacers = 0;
  for (const element of Array.from(section.children)) {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    if (element.classList.contains(PAGE_BREAK_CLASS)) {
      spacers += rect.height / zoom + parseFloat(style.marginTop) + parseFloat(style.marginBottom);
      continue;
    }
    flows.push({
      top: (rect.top - sectionTop) / zoom - contentTop - spacers,
      bottom: (rect.bottom - sectionTop) / zoom - contentTop - spacers,
      forced: style.breakBefore === "page",
    });
  }
  return pageStarts(flows, contentHeight);
}

export function measurePageBreaks(view: EditorView): PageBreakSpec[] {
  const starts = measurePageStarts(view.dom);
  let found = -1;
  let bodyStart = 0;
  let offset = 0;
  view.state.doc.forEach((node, _offset, index) => {
    if (found < 0 && node.type.name === "section" && node.attrs.part === BODY_PART) {
      found = index;
      bodyStart = offset + 1;
    }
    offset += node.nodeSize;
  });
  if (found < 0) return [];
  const body = view.state.doc.child(found);
  const specs: PageBreakSpec[] = [];
  let next = 0;
  body.content.forEach((_node, offset, index) => {
    if (next < starts.length && starts[next] === index) {
      specs.push({ pos: bodyStart + offset, page: next + 2 });
      next += 1;
    }
  });
  return specs;
}

export function pageMarker(label: string): HTMLElement {
  const marker = document.createElement("div");
  marker.className = PAGE_BREAK_CLASS;
  marker.setAttribute("aria-hidden", "true");
  marker.setAttribute("contenteditable", "false");
  const chip = document.createElement("span");
  chip.className = "document-page-break-label";
  chip.textContent = label;
  marker.append(chip);
  return marker;
}

/** Rebuild visual-only boundaries after laying out the unscaled fill preview. */
export function paginatePreview(dom: HTMLElement, label: (page: number) => string): void {
  dom.querySelectorAll(`.${PAGE_BREAK_CLASS}`).forEach(marker => marker.remove());
  const starts = measurePageStarts(dom);
  const section = dom.querySelector(`:scope > section[data-part="${BODY_PART}"]`);
  if (!section) return;
  const blocks = Array.from(section.children);
  starts.forEach((index, page) => blocks[index].before(pageMarker(label(page + 2))));
}

export function breakDecorations(
  doc: EditorNode,
  specs: PageBreakSpec[],
  label: (page: number) => string,
): DecorationSet {
  return DecorationSet.create(
    doc,
    specs
      .filter(spec => spec.pos > 0 && spec.pos < doc.content.size)
      .map(spec =>
        Decoration.widget(
          spec.pos,
          () => {
            return pageMarker(label(spec.page));
          },
          { side: -1 },
        ),
      ),
  );
}

// Page numbers are assigned consecutively from 2 by measurePageBreaks.
function sameSpecs(applied: PageBreakSpec[], measured: PageBreakSpec[]): boolean {
  return (
    applied.length === measured.length &&
    applied.every((spec, index) => spec.pos === measured[index].pos)
  );
}

/** Visual-only pagination. Markers live in decorations, never in the saved document. */
export function pageBreakPlugin(
  label: () => (page: number) => string,
  control: { refresh: (force?: boolean) => void },
): Plugin<DecorationSet> {
  const key = new PluginKey<DecorationSet>("page-breaks");
  return new Plugin<DecorationSet>({
    key,
    state: {
      init: () => DecorationSet.empty,
      apply(transaction, value) {
        const specs = transaction.getMeta(key) as PageBreakSpec[] | undefined;
        if (specs) return breakDecorations(transaction.doc, specs, label());
        return transaction.docChanged ? value.map(transaction.mapping, transaction.doc) : value;
      },
    },
    props: { decorations: editorState => key.getState(editorState) },
    view(view) {
      let applied: PageBreakSpec[] = [];
      let cancel: (() => void) | null = null;
      const run = (force = false) => {
        cancel = null;
        if (!view.dom.isConnected) return;
        const specs = measurePageBreaks(view);
        if (!force && sameSpecs(applied, specs)) return;
        applied = specs;
        view.dispatch(view.state.tr.setMeta(key, specs).setMeta("addToHistory", false));
      };
      const schedule = () => {
        if (cancel) return;
        if (typeof requestAnimationFrame === "function") {
          const frame = requestAnimationFrame(() => run());
          cancel = () => cancelAnimationFrame(frame);
        } else {
          const timer = setTimeout(() => run(), 20);
          cancel = () => clearTimeout(timer);
        }
      };
      control.refresh = run;
      const observer = typeof ResizeObserver === "function" ? new ResizeObserver(() => schedule()) : null;
      observer?.observe(view.dom);
      document.fonts?.ready.then(schedule).catch(() => {});
      schedule();
      return {
        update(view, previous) {
          if (!previous.doc.eq(view.state.doc)) schedule();
        },
        destroy() {
          control.refresh = () => {};
          cancel?.();
          observer?.disconnect();
        },
      };
    },
  });
}
