import { EditorState, TextSelection } from "prosemirror-state";
import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { mountEditor, type EditorPresentation } from "../src/editor/adapter";
import { editorSchema } from "../src/editor/model";
import { suggestFieldLabel } from "../src/editor/transactions";
import { FIELD_LABEL_LIMIT } from "../src/editor/fieldProperties";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { value: () => new DOMRect(), configurable: true });
});

function stateAround(paragraphText: string, characterStart: number, characterEnd: number) {
  const doc = editorSchema.nodeFromJSON({ type: "doc", content: [
    { type: "paragraph" },
    { type: "paragraph", content: [{ type: "text", text: paragraphText }] },
  ] });
  const state = EditorState.create({ schema: editorSchema, doc });
  // The second paragraph's text content starts one position inside its open gate.
  let textStart = 0;
  state.doc.forEach((node, offset, index) => { if (index === 1) textStart = offset + 1; });
  return state.apply(state.tr.setSelection(TextSelection.create(state.doc, textStart + characterStart, textStart + characterEnd)));
}

describe("suggested field labels", () => {
  test("the preceding label text prefills the name without its leading numbering", () => {
    const state = stateAround("3. П.І.Б. пацієнта ІВАНОВ ВІТАЛІЙ", "3. П.І.Б. пацієнта ".length, ("3. П.І.Б. пацієнта ІВАНОВ").length);
    expect(suggestFieldLabel(state)).toBe("П.І.Б. пацієнта");
  });

  test("plain preceding text is kept as-is and whitespace collapses", () => {
    const state = stateAround("Місце \n проживання:  Київ", "Місце \n проживання: ".length, "Місце \n проживання:  Київ".length);
    expect(suggestFieldLabel(state)).toBe("Місце проживання:");
  });

  test("an empty selection or a selection without preceding text suggests nothing", () => {
    const collapsed = stateAround("3. ІВАНОВ", 5, 5);
    expect(suggestFieldLabel(collapsed)).toBe("");
    const noBefore = stateAround("ІВАНОВ", 0, "ІВАНОВ".length);
    expect(suggestFieldLabel(noBefore)).toBe("");
  });

  test("suggestions are clipped to the label limit and stay valid", () => {
    const preceding = `${"Ґ".repeat(FIELD_LABEL_LIMIT + 20)} `;
    const state = stateAround(`${preceding}ІВАНОВ`, preceding.length, preceding.length + "ІВАНОВ".length);
    const suggestion = suggestFieldLabel(state);
    expect([...suggestion].length).toBe(FIELD_LABEL_LIMIT);
    expect(suggestion.startsWith("ҐҐ")).toBe(true);
  });
});

describe("retained selection while naming a field", () => {
  function mount() {
    const host = document.createElement("div");
    document.body.appendChild(host);
    const updates: EditorPresentation[] = [];
    const changed = vi.fn();
    const adapter = mountEditor(host, structuredClone(corpus) as object, {
      canEdit: () => true,
      onChange: changed,
      onUpdate: presentation => updates.push(presentation),
    });
    return { host, adapter, updates, changed };
  }

  test("an explicit retain keeps the chosen range highlighted without dirtying the document", () => {
    const { host, adapter, updates, changed } = mount();
    const first = updates[0].fields[0];
    expect(adapter.focusField(first.id)).toBe(true);
    adapter.retainSelection(true);
    expect(host.querySelector(".document-selection-retained")).not.toBeNull();
    expect(changed).not.toHaveBeenCalled();
    adapter.retainSelection(false);
    expect(host.querySelector(".document-selection-retained")).toBeNull();
    adapter.destroy();
    host.remove();
  });

  test("the retention clears itself when the document selection changes", () => {
    const { host, adapter, updates } = mount();
    const [first, second] = updates[0].fields;
    adapter.focusField(first.id);
    adapter.retainSelection(true);
    expect(host.querySelector(".document-selection-retained")).not.toBeNull();
    adapter.focusField(second.id);
    expect(host.querySelector(".document-selection-retained")).toBeNull();
    adapter.destroy();
    host.remove();
  });
});

describe("creation tools", () => {
  test("creating a field keeps the ordinary flow working", async () => {
    render(<I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} /></I18nextProvider>);
    await screen.findByRole("textbox", { name: "Editable document" });
    const input = screen.getByLabelText("New field label");
    fireEvent.change(input, { target: { value: "Пошта" } });
    expect(input).toHaveValue("Пошта");
  });
});
