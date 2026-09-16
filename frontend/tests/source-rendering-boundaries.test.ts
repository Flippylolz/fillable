import { DOMParser } from "prosemirror-model";
import { EditorState, NodeSelection } from "prosemirror-state";
import { editorSchema as schema } from "../src/editor/model";
import { sourceRules } from "../src/editor/SourceLayout";
import { sourceNodeView } from "../src/editor/sourceNodes";
import { isLightFill, lineSnapDelta, toggleSelectedCheckbox } from "../src/editor/checkboxes";

afterEach(() => document.body.replaceChildren());

test.each(["not json", "null", "1", "[]", '{"0":"#123456","1":42}'])
("pasted locked shape metadata is parsed conservatively: %s", raw => {
  const host = document.createElement("div");
  const paragraph = document.createElement("p");
  const span = document.createElement("span");
  span.dataset.locked = "shape"; span.dataset.shapes = raw; span.textContent = "Kept";
  paragraph.append(span); host.append(paragraph);
  const parsed = DOMParser.fromSchema(schema).parse(host);
  let found: Record<string, string> | undefined;
  parsed.descendants(node => { if (node.type.name === "lockedInline") found = node.attrs.shapes; });
  expect(found).toEqual(raw.startsWith('{') ? { "0": "#123456" } : {});
});

test.each([true, false])("native checkbox DOM preserves its checked state (%s)", checked => {
  const host = document.createElement("div");
  host.innerHTML = `<p><span class="document-checkbox" data-source="cb" data-checked="${checked}">box</span></p>`;
  const parsed = DOMParser.fromSchema(schema).parse(host);
  let state: boolean | undefined;
  parsed.descendants(node => { if (node.type.name === "checkbox") state = node.attrs.checked; });
  expect(state).toBe(checked);
});

test("layout CSS rejects unsupported positioning, floats and display modes", () => {
  const rules = sourceRules("safe", { nodes: { p: { display: "block", float: "right", clear: "left" } } });
  expect(rules).not.toMatch(/display:block|float:right|clear:left/);
  expect(sourceRules("safe", { nodes: { p: { display: "inline-table", float: "left", clear: "both" } } }))
    .toContain("display:inline-table!important;float:left!important;clear:both!important");
});

test("checkbox command queries do not mutate state and non-checkbox leaves fall through", () => {
  const make = (kind: "checkbox" | "lockedInline") => {
    const node = schema.nodes[kind].create({ id: "leaf", label: "kept" });
    const doc = schema.nodes.doc.create(null, schema.nodes.section.create({ part: "word/document.xml" },
      schema.nodes.paragraph.create({ id: "p" }, node)));
    const state = EditorState.create({ doc });
    return state.apply(state.tr.setSelection(NodeSelection.create(doc, 2)));
  };
  const state = make("checkbox");
  expect(toggleSelectedCheckbox(state)).toBe(true);
  expect((state.selection as NodeSelection).node.attrs.checked).toBe(false);
  expect(toggleSelectedCheckbox(make("lockedInline"))).toBe(false);
  expect(isLightFill("invalid")).toBe(true);
  expect(lineSnapDelta([{ top: 10, bottom: 20 }, { top: 50, bottom: 60 }], 12, 10, 1)).toBe(-2);
});

function snapping(top: number, paragraphStyle = "relative") {
  const callbacks: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => { callbacks.push(callback); return callbacks.length; }));
  const view = sourceNodeView({ locked: { shape: { text: "label", shapes: [
    { x: 0, y: top, width: 10, height: 10, fill: "#ffffff" },
  ] } } }, () => "Checkbox")(schema.nodes.lockedInline.create({ id: "shape", label: "" }));
  const paragraph = document.createElement("p");
  paragraph.style.position = paragraphStyle;
  paragraph.append("First ", document.createTextNode("second"), view.dom);
  document.body.append(paragraph);
  const box = (view.dom as HTMLElement).querySelector<HTMLElement>(".document-shape")!;
  return { callbacks, paragraph, box, frame: () => callbacks.shift()!(0) };
}

test("drawing alignment merges overlapping text runs and snaps to the nearest wrapped line", () => {
  const { paragraph, box, frame } = snapping(4);
  paragraph.style.zoom = "2";
  vi.spyOn(box, "getBoundingClientRect").mockReturnValue(new DOMRect(0, 40, 10, 12));
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [
    new DOMRect(0, 0, 0, 10), new DOMRect(0, 0, 10, 0),
    new DOMRect(0, 20, 20, 15), new DOMRect(20, 22, 20, 16), new DOMRect(0, 60, 20, 16),
  ] });
  frame();
  expect(parseFloat(box.style.top)).toBeCloseTo(4 * 4 / 3 + (23 - 40) / 2);
});

test("aligned shapes retain their authored offset and hidden layouts retry only 60 frames", () => {
  const { box, callbacks, frame } = snapping(5);
  vi.spyOn(box, "getBoundingClientRect").mockReturnValue(new DOMRect(0, 23, 10, 12));
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [new DOMRect(0, 20, 20, 18)] });
  frame();
  expect(box.style.top).toBe("5pt");
  expect(callbacks).toHaveLength(0);
  const hidden = snapping(5);
  for (let n = 0; n < 60; n++) hidden.frame();
  expect(hidden.callbacks).toHaveLength(0);
});

test("alignment skips detached, unpositioned and textless drawing hosts", () => {
  const staticHost = snapping(2, "static"); staticHost.frame();
  expect(staticHost.callbacks).toHaveLength(0);
  const detached = snapping(2); detached.paragraph.remove(); detached.frame();
  expect(detached.callbacks).toHaveLength(0);
  vi.stubGlobal("requestAnimationFrame", undefined);
  const view = sourceNodeView({ locked: { shape: { shapes: [
    { x: 0, y: 0, width: 10, height: 10, fill: "#ffffff" },
  ] } } }, () => "")(schema.nodes.lockedInline.create({ id: "shape", label: "", shapes: null }));
  expect((view.dom as HTMLElement).querySelector(".document-shape")).not.toHaveAttribute("aria-label");
});

test("missing presentation entries retain their label and zero zoom uses source scale",()=>{
  const view=sourceNodeView({},()=>"")(schema.nodes.lockedInline.create({id:"missing",label:"Preserved"}));
  expect(view.dom.textContent).toBe("Preserved");
  const {paragraph,box,frame}=snapping(5);paragraph.style.zoom="0";
  vi.spyOn(box,"getBoundingClientRect").mockReturnValue(new DOMRect(0,20,10,10));
  Object.defineProperty(Range.prototype,"getClientRects",{configurable:true,value:()=>[new DOMRect(0,20,20,20)]});
  frame();expect(parseFloat(box.style.top)).toBeCloseTo(5*4/3+5);
});

test("unsupported blocks render a noneditable block container",()=>{
  const view=sourceNodeView(undefined,()=>"")(schema.nodes.lockedBlock.create({id:"block",label:"Preserved block"}));
  expect((view.dom as HTMLElement).tagName).toBe("DIV");expect(view.dom.textContent).toBe("Preserved block");expect((view.dom as HTMLElement).contentEditable).toBe("false");
});
