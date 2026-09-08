import { act, fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { EditorState, TextSelection } from "prosemirror-state";
import { history, undo, redo } from "prosemirror-history";
import { editorSchema as schema } from "../src/editor/model";
import { fillBoxedDate } from "../src/editor/boxedDates";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { i18n, setLanguage } from "../src/i18n";

function paragraph(value: string, id = "p") {
  return schema.nodes.paragraph.create({id}, value ? schema.text(value, [schema.marks.source.create({id:`run:${id}`,bold:true})]) : []);
}
function state(nodes = [paragraph("1 │ 5 │ 1 │ 1 │ 8 │ 3")]) {
  const doc = schema.nodes.doc.create(null, schema.nodes.section.create({part:"word/document.xml"}, nodes));
  let result = EditorState.create({doc,plugins:[history()]});
  if (nodes[0].type.name === "paragraph") result = result.apply(result.tr.setSelection(TextSelection.create(doc, 2, doc.content.size - 2)));
  return result;
}
function table(values: string[]) {
  return schema.nodes.table.create({id:"table"}, schema.nodes.tableRow.create({id:"row"}, values.map((value,i) => schema.nodes.tableCell.create({id:`c${i}`},paragraph(value,`p${i}`)))));
}
function selectCells(current: EditorState) {
  const positions: number[] = [];
  current.doc.descendants((node,pos) => { if(node.type.name === "paragraph") positions.push(pos); });
  return current.apply(current.tr.setSelection(TextSelection.create(current.doc,positions[0]+1,positions[positions.length-1]+1)));
}

test("one valid date replaces separated digits without losing outlines, marks, or undo history", () => {
  let current = state(); const original = current.doc;
  const result = fillBoxedDate(current,"2024-02-29"); expect(result.issue).toBeUndefined();
  current = current.apply(result.transaction!);
  expect(current.doc.textContent).toBe("2 │ 9 │ 0 │ 2 │ 2 │ 4");
  expect(current.doc.firstChild!.firstChild!.firstChild!.marks[0].attrs.bold).toBe(true);
  expect(undo(current,tr => { current=current.apply(tr); })).toBe(true);
  expect(current.doc.eq(original)).toBe(true);
  expect(redo(current,tr => { current=current.apply(tr); })).toBe(true);
  expect(current.doc.textContent).toBe("2 │ 9 │ 0 │ 2 │ 2 │ 4");
});

test("eight boxes and grouped day/month/year cells retain cell identities", () => {
  for(const values of [Array(8).fill(""), ["01","01","2000"], Array(6).fill("_"), ["01","01","00"]]) {
    const current=selectCells(state([table(values)]));
    const result=fillBoxedDate(current,"2026-01-23");
    expect(result.issue).toBeUndefined();
    const next=current.apply(result.transaction!);
    const count=values.length===3 ? values.join("").length : values.length;
    expect(next.doc.textContent).toBe(count===6?"230126":"23012026");
    expect(next.doc.firstChild!.firstChild!.attrs.id).toBe("table");
    expect(next.doc.firstChild!.firstChild!.firstChild!.firstChild!.attrs.id).toBe("c0");
  }
  const current=state([paragraph("_ | _ | _ | _ | _ | _ | _ | _")]);
  expect(current.apply(fillBoxedDate(current,"2000-02-29").transaction!).doc.textContent).toBe("2 | 9 | 0 | 2 | 2 | 0 | 0 | 0");
});

test("invalid dates, ambiguous text, protected fields and wrong table sizes cannot mutate", () => {
  for(const date of ["1900-02-29","2023-02-29","2026-13-01","0000-01-01","2026-04-31","2026-00-01","2026-01-00","bad"]) expect(fillBoxedDate(state(),date).issue).toBe("invalid_date");
  for(const content of ["123456","Date 1 | 2 | 3 | 4 | 5 | 6", "1 | 2 | 3"]) expect(fillBoxedDate(state([paragraph(content)]),"2026-01-23").issue).toBe("select_boxes");
  for(const values of [["1","2"], ["12","1","1","1","1","1"], ["day","01","2000"]]) expect(fillBoxedDate(selectCells(state([table(values)])),"2026-01-23").issue).toBe("select_boxes");
  const protectedNode=schema.nodes.paragraph.create({id:"locked"}, schema.nodes.lockedInline.create({id:"drawing",label:"1|2|3|4|5|6"}));
  expect(fillBoxedDate(state([protectedNode]),"2026-01-23").issue).toBe("select_boxes");
});

test("localized date action fills the actual editor selection and respects read-only state", async () => {
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
  await setLanguage("en"); const reader=vi.fn(),change=vi.fn();
  const ui=(readOnly=false)=><I18nextProvider i18n={i18n}><DocumentEditor initialDocument={state().doc.toJSON()} readOnly={readOnly} onReader={reader} onSnapshot={change}/></I18nextProvider>;
  const view=render(ui());
  fireEvent.change(screen.getByLabelText("Date in boxes"),{target:{value:"2026-01-23"}});
  fireEvent.click(screen.getByRole("button",{name:"Fill selected date boxes"}));
  expect(screen.getByRole("alert")).toHaveTextContent("Select only");
  const editor=view.container.querySelector(".ProseMirror p")!;
  (view.container.querySelector(".ProseMirror") as HTMLElement).focus();
  const range=document.createRange(); range.selectNodeContents(editor);
  const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range);
  await act(async()=>{document.dispatchEvent(new Event("selectionchange"));});
  fireEvent.click(screen.getByRole("button",{name:"Fill selected date boxes"}));
  expect(reader.mock.calls[0][0]().document.content[0].content[0].content.map((n:{text:string})=>n.text).join("")).toBe("2 │ 3 │ 0 │ 1 │ 2 │ 6");
  view.rerender(ui(true));
  expect(screen.getByRole("button",{name:"Fill selected date boxes"})).toBeDisabled();
  expect(change).toHaveBeenCalled();
});
