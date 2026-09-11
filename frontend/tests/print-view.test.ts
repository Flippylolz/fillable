import { printDocumentNode } from "../src/workspace/printView";

const original = document.createElement.bind(document);
const layout = { rules: `[data-layout=":r1:"] .ProseMirror{color:red}`, scope: ":r1:" };

function stubFrame(print: (() => void) | null, withDocument = true) {
  const writes: string[] = [];
  const printSpy = print ? vi.fn(print) : vi.fn();
  const createElement = vi.spyOn(document, "createElement").mockImplementation((tag, options) => {
    const element = original(tag as string, options);
    if (tag === "iframe") {
      Object.defineProperty(element, "contentWindow", { value: print ? { print: printSpy, addEventListener: vi.fn(), focus: vi.fn() } : null });
      Object.defineProperty(element, "contentDocument", { value: withDocument && print ? { open: vi.fn(), write: (text: string) => writes.push(text), close: vi.fn() } : null });
    }
    return element;
  });
  return { writes, printSpy, restore: () => createElement.mockRestore() };
}

test("print writes the layout rules and the node clone without page-break markers, then prints", () => {
  const node = original("div");
  node.innerHTML = `<p>Заява</p><div class="document-page-break" aria-hidden="true"></div><p>Кінець</p>`;
  const frame = stubFrame(() => {});
  try {
    expect(printDocumentNode(node, layout)).toBe(true);
    expect(frame.printSpy).toHaveBeenCalledTimes(1);
    expect(frame.writes).toHaveLength(1);
    expect(frame.writes[0]).toContain(layout.rules);
    expect(frame.writes[0]).toContain(`data-layout=":r1:"`);
    expect(frame.writes[0]).toContain("Заява");
    expect(frame.writes[0]).not.toContain("document-page-break");
  } finally { frame.restore(); }
});

test("print reports unavailable when the frame window or document is missing", () => {
  const node = original("div");
  const noWindow = stubFrame(null);
  try { expect(printDocumentNode(node, layout)).toBe(false); expect(noWindow.printSpy).not.toHaveBeenCalled(); }
  finally { noWindow.restore(); }
  const noDocument = stubFrame(() => {}, false);
  try { expect(printDocumentNode(node, layout)).toBe(false); }
  finally { noDocument.restore(); }
});

test("print reports unavailable when the browser rejects printing", () => {
  const node = original("div");
  node.innerHTML = "<p>Заява</p>";
  const frame = stubFrame(() => { throw new Error("blocked"); });
  try {
    expect(printDocumentNode(node, layout)).toBe(false);
    expect(frame.printSpy).toHaveBeenCalledTimes(1);
  } finally { frame.restore(); }
});

test("print without a node reports unavailable without creating a frame", () => {
  const createElement = vi.spyOn(document, "createElement");
  try {
    expect(printDocumentNode(null, layout)).toBe(false);
    expect(createElement).not.toHaveBeenCalledWith("iframe");
  } finally { createElement.mockRestore(); }
});
