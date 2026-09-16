import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { DocumentEditor, type PrintSource } from "../src/editor/DocumentEditor";
import { CopyPrompt } from "../src/workspace/CopyPrompt";
import { setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import discovery from "../prototype/fields.json";
import type { components } from "../generated/api";

beforeEach(async()=>{
  await setLanguage("en");
  Object.defineProperty(Range.prototype,"getClientRects",{configurable:true,value:()=>[]});
  Object.defineProperty(Range.prototype,"getBoundingClientRect",{configurable:true,value:()=>new DOMRect()});
});

test("fill form focuses and removes occurrences, and supports undo and redo",()=>{
  const view=render(<DocumentEditor initialDocument={corpus} mode="fill"/>);
  const form=within(view.container.querySelector(".fill-form")!);
  const before=form.getAllByRole("article").length;
  fireEvent.click(form.getAllByRole("button",{name:/Go to field:/})[0]);
  expect(view.container.querySelector('.fill-entry[data-active="true"]')).not.toBeNull();
  fireEvent.click(form.getAllByRole("button",{name:/Remove field:/})[0]);
  expect(form.getAllByRole("article")).toHaveLength(before-1);
  fireEvent.click(form.getByRole("button",{name:"Undo"}));
  expect(form.getAllByRole("article")).toHaveLength(before);
  fireEvent.click(form.getByRole("button",{name:"Redo"}));
  expect(form.getAllByRole("article")).toHaveLength(before-1);
});

test("fill mode reports inconsistent linked values and stale review in either reopen configuration",()=>{
  const doc=structuredClone(corpus);
  let changed=false;
  function visit(node: {type:string;content?:unknown[];text?:string}) {
    if(node.type==="field"&&!changed){node.content=[{type:"text",text:"Mismatch"}];changed=true;}
    else node.content?.forEach(child=>visit(child as typeof node));
  }
  visit(doc);
  const props={initialDocument:doc,mode:"fill" as const,sourceVersion:"wrong-version",discoverySnapshot:discovery as components["schemas"]["FieldSnapshot"]};
  const view=render(<DocumentEditor {...props}/>);
  expect(view.container.querySelectorAll(".fill-form .field-conflict").length).toBeGreaterThan(0);
  expect(view.container.querySelector(".fill-review-stale")).toHaveTextContent(/reopen/i);
  const reopen=vi.fn();view.rerender(<DocumentEditor {...props} onReopen={reopen}/>);
  fireEvent.click(within(view.container.querySelector(".fill-review-stale")!).getByRole("button"));
  expect(reopen).toHaveBeenCalledOnce();
});

test("print reader becomes unavailable after unmount and fill preview tolerates a removed canvas",async()=>{
  vi.useFakeTimers();
  let reader:(()=>PrintSource|null)|null=null;
  const receive=vi.fn((value:typeof reader)=>{if(value)reader=value;});
  const view=render(<DocumentEditor initialDocument={corpus} mode="fill" onPrintReader={receive}/>);
  expect(reader!()!.node).toHaveClass("ProseMirror");
  reader!()!.node.remove();
  await act(async()=>{await vi.advanceTimersByTimeAsync(750);});
  expect(reader!()).toBeNull();
  view.unmount();expect(receive).toHaveBeenLastCalledWith(null);expect(reader!()).toBeNull();
  vi.useRealTimers();
});

test("copy prompt rejects blank titles and submission while busy or disabled",()=>{
  const submit=vi.fn();const props={initialTitle:" ",busy:false,error:"",onSubmit:submit,onCancel:vi.fn()};
  const view=render(<CopyPrompt {...props}/>);
  fireEvent.submit(view.container.querySelector("form")!);
  expect(screen.getByRole("alert")).toBeVisible();expect(submit).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("textbox"),{target:{value:"  Copy  "}});
  view.rerender(<CopyPrompt {...props} busy/>);fireEvent.submit(view.container.querySelector("form")!);
  view.rerender(<CopyPrompt {...props} disabled/>);fireEvent.submit(view.container.querySelector("form")!);
  expect(submit).not.toHaveBeenCalled();
  view.rerender(<CopyPrompt {...props}/>);fireEvent.submit(view.container.querySelector("form")!);
  expect(submit).toHaveBeenCalledWith("Copy");
});

test("checkbox action reports editing access lost after selection",async()=>{
  let allowed=true;
  const initialDocument={type:"doc",content:[{type:"section",attrs:{part:"word/document.xml"},content:[{type:"paragraph",attrs:{id:"p"},content:[{type:"text",text:"☐"}]}]}]};
  const view=render(<DocumentEditor initialDocument={initialDocument} canEdit={()=>allowed}/>);
  const paragraph=view.container.querySelector(".ProseMirror p")!;
  (view.container.querySelector(".ProseMirror") as HTMLElement).focus();
  const range=document.createRange();range.selectNodeContents(paragraph);const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range);
  await act(async()=>document.dispatchEvent(new Event("selectionchange")));
  const button=screen.getByRole("button",{name:"Toggle checkbox"});expect(button).toBeEnabled();allowed=false;fireEvent.click(button);
  expect(screen.getByRole("alert")).toBeVisible();expect(paragraph.textContent).toBe("☐");
});

test("focusing the field label preserves the selected source text highlight",async()=>{
  const view=render(<DocumentEditor initialDocument={corpus}/>);
  const paragraph=view.container.querySelector(".ProseMirror p")!;(view.container.querySelector(".ProseMirror") as HTMLElement).focus();
  const range=document.createRange();range.selectNodeContents(paragraph);const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range);
  await act(async()=>document.dispatchEvent(new Event("selectionchange")));
  fireEvent.focus(screen.getByRole("textbox",{name:"New field label"}));expect(view.container.querySelector(".document-selection-retained")).not.toBeNull();
});
