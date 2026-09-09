import { EditorState, TextSelection, NodeSelection } from "prosemirror-state";
import { history, undo } from "prosemirror-history";
import { editorSchema as schema } from "../src/editor/model";
import { toggleGlyphCheckbox, glyphSwap, glyphCheckboxReady, toggleSelectedCheckbox, shapeToggleFill, DRAWN_CHECKED_FALLBACK, DRAWN_UNCHECKED_FILL } from "../src/editor/checkboxes";
import { sourceNodeView } from "../src/editor/sourceNodes";
import type { SourcePresentation } from "../src/editor/SourceLayout";

function paragraph(content: (string | ReturnType<typeof schema.nodes.checkbox.create>)[] = ["check ", schema.nodes.checkbox.create({ id: "cb1", checked: false }), " end"], id = "p") {
  return schema.nodes.paragraph.create(
    { id },
    content.map(part =>
      typeof part === "string"
        ? schema.text(part, [schema.marks.source.create({ id: `run:${id}`, bold: true })])
        : part,
    ),
  );
}

function state(nodes = [paragraph()]) {
  const doc = schema.nodes.doc.create(null, schema.nodes.section.create({ part: "word/document.xml" }, nodes));
  return EditorState.create({ doc, plugins: [history()] });
}

function checkboxPosition(current: EditorState): number {
  let found = 0;
  current.doc.descendants((node, pos) => { if (!found && node.type.name === "checkbox") found = pos; });
  return found;
}

test("ballot-box pairs swap both ways; other characters have no pair", () => {
  expect(glyphSwap("☐")).toBe("☒");
  expect(glyphSwap("☒")).toBe("☐");
  expect(glyphSwap("q")).toBeNull();
  expect(glyphSwap("¨")).toBeNull();
});

test("one selected box swaps while preserving run formatting and undoing in one step", () => {
  // Text "a ☐ b" starts at document position 2, so the box occupies position 4.
  let current = state([paragraph(["a ☐ b"])]);
  current = current.apply(current.tr.setSelection(TextSelection.create(current.doc, 4, 5)));
  expect(glyphCheckboxReady(current)).toBe(true);
  const result = toggleGlyphCheckbox(current);
  expect(result.issue).toBeUndefined();
  const next = current.apply(result.transaction!);
  expect(next.doc.textContent).toBe("a ☒ b");
  const swapped = next.doc.firstChild!.firstChild!.firstChild!;
  expect(swapped.marks[0].attrs.bold).toBe(true);
  expect(undo(next, tr => { current = next.apply(tr); })).toBe(true);
  expect(current.doc.textContent).toBe("a ☐ b");
});

test("wrong selections never mutate the document", () => {
  const base = state([paragraph(["a ☐ b"])]);
  const wide = base.apply(base.tr.setSelection(TextSelection.create(base.doc, 4, 6)));
  expect(toggleGlyphCheckbox(wide).issue).toBe("select_box");
  expect(glyphCheckboxReady(wide)).toBe(false);
  const plain = state([paragraph(["no boxes"])]);
  const middle = plain.apply(plain.tr.setSelection(TextSelection.create(plain.doc, 4, 5)));
  expect(toggleGlyphCheckbox(middle).issue).toBe("select_box");
  // A two-character selection that crosses into a checkbox control stays untouched.
  const crossing = state([paragraph(["x", schema.nodes.checkbox.create({ id: "cb2", checked: false }), "y"])]);
  const boxPosition = checkboxPosition(crossing);
  const across = crossing.apply(crossing.tr.setSelection(TextSelection.create(crossing.doc, boxPosition - 1, boxPosition + 1)));
  expect(toggleGlyphCheckbox(across).issue).toBe("select_box");
  expect(across.doc.textContent).toBe(crossing.doc.textContent);
});

test("node selection on a checkbox control toggles its checked state", () => {
  let current = state();
  const boxPosition = checkboxPosition(current);
  current = current.apply(current.tr.setSelection(NodeSelection.create(current.doc, boxPosition)));
  expect(toggleSelectedCheckbox(current, tr => { current = current.apply(tr); })).toBe(true);
  const box = current.doc.firstChild!.firstChild!.child(1);
  expect(box.type.name).toBe("checkbox");
  expect(box.attrs.checked).toBe(true);
  // Space on plain text falls through instead of toggling anything.
  const plain = state([paragraph(["a ☐ b"])]);
  const textSelected = plain.apply(plain.tr.setSelection(TextSelection.create(plain.doc, 2, 3)));
  expect(toggleSelectedCheckbox(textSelected)).toBe(false);
});

test("checkbox nodes render role and state", () => {
  const render = (checked: boolean) =>
    schema.nodes.checkbox.spec.toDOM!(schema.nodes.checkbox.create({ id: `cb${checked ? 1 : 2}`, checked })) as [string, Record<string, string>, string];
  const [, checkedAttrs, checkedText] = render(true);
  expect(checkedAttrs.class).toBe("document-checkbox");
  expect(checkedAttrs["aria-checked"]).toBe("true");
  expect(checkedAttrs["data-source"]).toBe("cb1");
  expect(checkedText).toBe("☒");
  const [, uncheckedAttrs, uncheckedText] = render(false);
  expect(uncheckedAttrs["aria-checked"]).toBe("false");
  expect(uncheckedText).toBe("☐");
});

test("inline shape placements render in flow; anchored ones stay absolutely positioned", () => {
  const presentation: SourcePresentation = {
    nodes: {},
    section: {},
    locked: {
      "word/document.xml:1": {
        text: "",
        shapes: [
          { width: 10, height: 10, fill: "transparent", border: "0.5pt solid #000000", placement: "inline" },
          { x: 23.6, y: 2.4, width: 10, height: 10, fill: "transparent", placement: "absolute" },
          { width: 0, height: 10, fill: "transparent", placement: "inline" },
        ],
      },
    },
  };
  const host = document.createElement("div");
  const nodeView = sourceNodeView(presentation, () => "")(schema.nodes.lockedInline.create({ id: "word/document.xml:1", label: "" }));
  host.append(nodeView.dom);
  const boxes = (nodeView.dom as HTMLElement).querySelectorAll("span[style]");
  expect(boxes.length).toBe(2);
  expect((boxes[0] as HTMLElement).style.display).toBe("inline-block");
  expect((boxes[0] as HTMLElement).style.position).not.toBe("absolute");
  expect((boxes[1] as HTMLElement).style.position).toBe("absolute");
  expect((nodeView.dom as HTMLElement).classList.contains("document-quiet")).toBe(true);
  const labelled = sourceNodeView({locked:{"word/document.xml:1":{text:"note",shapes:[{width:10,height:10,fill:"transparent",placement:"inline"}]}}}, () => "")(schema.nodes.lockedInline.create({ id: "word/document.xml:1", label: "" }));
  expect((labelled.dom as HTMLElement).classList.contains("document-quiet")).toBe(false);
});

test("explicitly filled shapes render as togglable checkboxes with overrides", () => {
  const presentation: SourcePresentation = {
    nodes: {},
    section: {},
    locked: {
      "word/document.xml:1": {
        text: "",
        shapes: [
          { x: 4, y: 4, width: 9, height: 9, fill: "#938953", placement: "absolute" },
          { x: 8, y: 4, width: 9, height: 9, fill: "#ffffff", placement: "absolute" },
        ],
      },
    },
  };
  const node = schema.nodes.lockedInline.create({ id: "word/document.xml:1", label: "", shapes: { "1": "#595959" } });
  const dom = sourceNodeView(presentation, () => "Прапорець форми")(node).dom as HTMLElement;
  const boxes = dom.querySelectorAll<HTMLElement>("span.document-shape");
  expect(boxes.length).toBe(2);
  expect(boxes[0].dataset.fill).toBe("#938953");
  expect(boxes[0].getAttribute("aria-checked")).toBe("true");
  expect(boxes[0].getAttribute("aria-label")).toBe("Прапорець форми");
  expect(boxes[0].style.pointerEvents).toBe("auto");
  // The stored override replaces the authored fill of the second rectangle.
  expect(boxes[1].dataset.fill).toBe("#595959");
  expect(boxes[1].getAttribute("aria-checked")).toBe("true");
  const rendered = node.type.spec.toDOM!(node) as [string, Record<string, string>, string];
  expect(rendered[1]["data-shapes"]).toBe('{"1":"#595959"}');
  const plain = schema.nodes.lockedInline.create({ id: "word/document.xml:1", label: "" });
  const plainRendered = plain.type.spec.toDOM!(plain) as [string, Record<string, string>, string];
  expect(plainRendered[1]["data-shapes"]).toBeUndefined();
});

test("toggling a drawn rectangle flips light to the form's dark fill and back", () => {
  // A light box takes the dark fill used by its sibling rectangles.
  expect(shapeToggleFill("#ffffff", ["#938953", "#ffffff"])).toBe("#938953");
  // Without any dark sibling the bounded default marks the box as checked.
  expect(shapeToggleFill("#ffffff", ["#ffffff"])).toBe(DRAWN_CHECKED_FALLBACK);
  // A dark box returns to the cleared appearance.
  expect(shapeToggleFill("#938953", ["#938953"])).toBe(DRAWN_UNCHECKED_FILL);
  expect(shapeToggleFill("#595959", [])).toBe(DRAWN_UNCHECKED_FILL);
});
