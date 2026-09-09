import { mountEditor } from "../src/editor/adapter";
import { editorSchema } from "../src/editor/model";
import { PAGE_BREAK_CLASS, breakDecorations, pageStarts } from "../src/editor/pagination";
import corpus from "../prototype/document.json";

type PageStyle = Partial<Record<"minHeight" | "paddingTop" | "paddingBottom", string>>;

/**
 * Stub real layout without touching ProseMirror's DOM: body blocks get their
 * rect from their index among non-marker children, so ProseMirror redraws
 * cannot shift or erase it. `blocks` feeds tops/heights in document order.
 */
function stubLayout(zoom: string, page: PageStyle) {
  const realStyle = window.getComputedStyle.bind(window);
  const realRect = Element.prototype.getBoundingClientRect;
  const blocks: Array<{ top: number; height: number }> = [];
  const styleSpy = vi.spyOn(window, "getComputedStyle").mockImplementation((element: Element) => {
    const empty = { getPropertyValue: () => "" };
    if (element instanceof HTMLElement && element.classList.contains("ProseMirror"))
      return { ...empty, zoom } as unknown as CSSStyleDeclaration;
    if (element.matches('section[data-part="word/document.xml"]'))
      return { ...empty, ...page } as unknown as CSSStyleDeclaration;
    if (element.classList.contains(PAGE_BREAK_CLASS))
      return { ...empty, marginTop: "8px", marginBottom: "8px" } as unknown as CSSStyleDeclaration;
    return realStyle(element);
  });
  const rectSpy = vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
    if (this instanceof HTMLElement && this.classList.contains(PAGE_BREAK_CLASS)) return new DOMRect(0, 0, 100, 36);
    const parent = this.parentElement;
    if (parent?.matches('section[data-part="word/document.xml"]')) {
      const index = Array.from(parent.children).filter(child => !child.classList.contains(PAGE_BREAK_CLASS)).indexOf(this);
      return index >= 0 && blocks[index] ? new DOMRect(0, blocks[index].top, 100, blocks[index].height) : realRect.call(this);
    }
    return realRect.call(this);
  });
  return { blocks, restore: () => { styleSpy.mockRestore(); rectSpy.mockRestore(); } };
}

function stackBlocks(layout: { blocks: Array<{ top: number; height: number }> }, count: number, height = 400, start = 50) {
  let top = start;
  for (let index = 0; index < count; index += 1) {
    layout.blocks.push({ top, height });
    top += height;
  }
}

const settle = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(null))));
const markers = (host: HTMLElement) => host.querySelectorAll<HTMLElement>(`.${PAGE_BREAK_CLASS}`);

test("pageStarts breaks after blocks that pass each page's content height", () => {
  const flow = (top: number) => ({ top });
  expect(pageStarts([], 100)).toEqual([]);
  expect(pageStarts([flow(0), flow(40), flow(90)], 100)).toEqual([]);
  expect(pageStarts([flow(0), flow(40), flow(120), flow(160)], 100)).toEqual([2]);
  expect(pageStarts([flow(0), flow(50), flow(250), flow(300), flow(550)], 200)).toEqual([2, 4]);
  // A block starting exactly at the page bottom stays on that page.
  expect(pageStarts([flow(0), flow(100)], 100)).toEqual([]);
  // One block taller than a page pushes the next block to a new page.
  expect(pageStarts([flow(0), flow(50), flow(300)], 100)).toEqual([2]);
});

test("markers appear between blocks that begin a new page and update their label", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("1", { minHeight: "1000px", paddingTop: "50px", paddingBottom: "50px" });
  let fieldId = "";
  const editor = mountEditor(host, structuredClone(corpus), {
    onChange: vi.fn(),
    onUpdate: presentation => {
      fieldId = presentation.fields[0]?.id ?? fieldId;
    },
  });
  try {
    stackBlocks(layout, 6);
    const body = host.querySelector('section[data-part="word/document.xml"]')!;
    const blocks = [...body.querySelectorAll(":scope > *")];
    await settle();
    expect(markers(host)).toHaveLength(1);
    const marker = markers(host)[0];
    expect(marker.parentElement).toBe(body);
    expect(marker.getAttribute("aria-hidden")).toBe("true");
    expect(marker.getAttribute("contenteditable")).toBe("false");
    // The default label is the bare page number until the localized one arrives.
    expect(marker.textContent).toBe("2");
    expect(marker.nextElementSibling).toBe(blocks[3]);
    // A document change keeps the mapped markers and recomputes without drift.
    editor.setPageBreakLabel(page => `Сторінка ${page}`);
    editor.focusField(fieldId);
    editor.updateField("ПІБ_КЛІЄНТА", "Ґанна Маєвська");
    await settle();
    expect(markers(host)).toHaveLength(1);
    expect(host.querySelector(".document-page-break-label")?.textContent).toBe("Сторінка 2");
    // The rewritten paragraph is a fresh element; its source identity is stable.
    expect(markers(host)[0].nextElementSibling?.getAttribute("data-source")).toBe(blocks[3].getAttribute("data-source"));
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("markers number every page boundary in order", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("1", { minHeight: "1000px", paddingTop: "50px", paddingBottom: "50px" });
  const editor = mountEditor(host, structuredClone(corpus), { onChange: vi.fn(), onUpdate: vi.fn() });
  try {
    stackBlocks(layout, 10);
    await settle();
    const found = markers(host);
    expect(found).toHaveLength(3);
    expect([...found].map(marker => marker.textContent)).toEqual(["2", "3", "4"]);
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("marker positions follow the source zoom scale", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("2", { minHeight: "1000px", paddingTop: "50px", paddingBottom: "50px" });
  const editor = mountEditor(host, structuredClone(corpus), { onChange: vi.fn(), onUpdate: vi.fn() });
  try {
    stackBlocks(layout, 6, 800, 100);
    await settle();
    expect(markers(host)).toHaveLength(1);
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("documents without source page geometry show no markers", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("not-a-number", { minHeight: "", paddingTop: "", paddingBottom: "" });
  const editor = mountEditor(host, structuredClone(corpus), { onChange: vi.fn(), onUpdate: vi.fn() });
  try {
    stackBlocks(layout, 6);
    await settle();
    expect(markers(host)).toHaveLength(0);
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("collapsed and missing body pages show no markers", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("1", { minHeight: "100px", paddingTop: "80px", paddingBottom: "80px" });
  const editor = mountEditor(host, structuredClone(corpus), { onChange: vi.fn(), onUpdate: vi.fn() });
  try {
    stackBlocks(layout, 6);
    await settle();
    expect(markers(host)).toHaveLength(0);
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("documents without a body section show no markers", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("1", { minHeight: "1000px", paddingTop: "50px", paddingBottom: "50px" });
  const parts = structuredClone(corpus) as typeof corpus;
  parts.content = parts.content.filter(section => section.attrs.part !== "word/document.xml");
  const editor = mountEditor(host, parts, { onChange: vi.fn(), onUpdate: vi.fn() });
  try {
    await settle();
    expect(markers(host)).toHaveLength(0);
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("destroying the editor cancels pending measurement", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("1", { minHeight: "1000px", paddingTop: "50px", paddingBottom: "50px" });
  const editor = mountEditor(host, structuredClone(corpus), { onChange: vi.fn(), onUpdate: vi.fn() });
  stackBlocks(layout, 6);
  editor.destroy();
  host.remove();
  await settle();
  expect(host.children).toHaveLength(0);
  layout.restore();
});

test("markers already in the flow are excluded from measurement", async () => {
  const host = document.createElement("div");
  document.body.append(host);
  const layout = stubLayout("1", { minHeight: "1000px", paddingTop: "50px", paddingBottom: "50px" });
  const editor = mountEditor(host, structuredClone(corpus), { onChange: vi.fn(), onUpdate: vi.fn() });
  try {
    stackBlocks(layout, 10);
    await settle();
    // Re-measure with markers present: their own height must not shift pages.
    editor.setPageBreakLabel(page => `P-${page}`);
    await settle();
    expect(markers(host)).toHaveLength(3);
    expect([...markers(host)].map(marker => marker.textContent)).toEqual(["P-2", "P-3", "P-4"]);
  } finally {
    editor.destroy();
    host.remove();
    layout.restore();
  }
});

test("break decorations ignore positions outside the document", () => {
  const doc = editorSchema.nodeFromJSON(structuredClone(corpus));
  const valid = breakDecorations(doc, [{ pos: 3, page: 2 }], page => `P${page}`);
  expect(valid.find()).toHaveLength(1);
  expect(valid.find()[0].from).toBe(3);
  const outside = breakDecorations(doc, [{ pos: 0, page: 2 }, { pos: doc.content.size + 5, page: 3 }], page => `P${page}`);
  expect(outside.find()).toHaveLength(0);
});
