import { EditorView } from "prosemirror-view";
import { TextSelection } from "prosemirror-state";
import { fireEvent } from "@testing-library/react";
import { mountEditor } from "../src/editor/adapter";
import { editorSchema as schema } from "../src/editor/model";
import type { SourcePresentation } from "../src/editor/SourceLayout";

const doc=(content: unknown[])=>({type:"doc",content:[{type:"section",attrs:{part:"word/document.xml"},content:[{type:"paragraph",attrs:{id:"p"},content}]}]});
function mounted(document:object=doc([{type:"checkbox",attrs:{id:"check",checked:false}},{type:"text",text:" ☐ 1|2|3|4|5|6"}]),presentation?:SourcePresentation) {
  const host=window.document.createElement("div");window.document.body.append(host);
  let view!:EditorView;let allowed=true;
  const original=EditorView.prototype.setProps;
  vi.spyOn(EditorView.prototype,"setProps").mockImplementation(function(this:EditorView,state){view=this;return original.call(this,state);});
  const change=vi.fn(),update=vi.fn();
  const editor=mountEditor(host,document,{presentation,canEdit:()=>allowed,onChange:change,onUpdate:update});
  editor.refreshAccess();
  return {host,view,editor,change,update,deny:()=>{allowed=false;},close:()=>{editor.destroy();host.remove();}};
}
beforeEach(()=>{
  Object.defineProperty(Range.prototype,"getClientRects",{configurable:true,value:()=>[]});
  Object.defineProperty(Range.prototype,"getBoundingClientRect",{configurable:true,value:()=>new DOMRect()});
});

test("native checkbox clicks toggle once, undo, and reject read-only or composing edits",()=>{
  const test=mounted();const {host,view,editor}=test;
  try {
    fireEvent.click(host.querySelector(".document-checkbox")!);
    expect(view.state.doc.nodeAt(2)!.attrs.checked).toBe(true);
    expect(editor.undo()).toBe(true);expect(view.state.doc.nodeAt(2)!.attrs.checked).toBe(false);
    fireEvent(view.dom,new CompositionEvent("compositionstart",{bubbles:true}));
    fireEvent.click(host.querySelector(".document-checkbox")!);
    expect(view.state.doc.nodeAt(2)!.attrs.checked).toBe(false);
    expect(editor.fillDate("2024-02-29")).toBe("read_only");expect(editor.toggleGlyph()).toBe("read_only");
    fireEvent(view.dom,new CompositionEvent("compositionstart",{bubbles:true}));
    test.deny();fireEvent.click(host.querySelector(".document-checkbox")!);
    expect(view.state.doc.nodeAt(2)!.attrs.checked).toBe(false);
  } finally{test.close();}
});

test("adapter glyph commands preserve text and reject unavailable selection or access",()=>{
  const test=mounted(doc([{type:"text",text:"☐ 1|2|3|4|5|6"}]));const {view,editor}=test;
  try {
    expect(editor.toggleGlyph()).toBe("select_box");
    view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc,2,3)));
    expect(editor.toggleGlyph()).toBeNull();expect(view.state.doc.textContent).toContain("☒");
    view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc,4,15)));
    expect(editor.fillDate("bad")).toBe("invalid_date");
    expect(editor.fillDate("2024-02-29")).toBeNull();expect(view.state.doc.textContent).toContain("2|9|0|2|2|4");
    test.deny();const before=view.state.doc;
    view.dispatch(view.state.tr.insertText("blocked",4));expect(view.state.doc).toBe(before);
    expect(editor.fillDate("2024-02-29")).toBe("read_only");expect(editor.toggleGlyph()).toBe("read_only");
  }finally{test.close();}
});

test("retained selection survives metadata-only updates and explicit clearing removes it",()=>{
  const test=mounted();const {view,editor}=test;
  try {
    view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc,4,5)));
    editor.retainSelection(true);expect(view.dom.querySelector(".document-selection-retained")).toHaveTextContent("☐");
    view.dispatch(view.state.tr.setMeta("external-state",true));
    expect(view.dom.querySelector(".document-selection-retained")).toHaveTextContent("☐");
    editor.retainSelection(false);expect(view.dom.querySelector(".document-selection-retained")).toBeNull();
  }finally{test.close();}
});

test("checkbox-looking DOM without a corresponding model checkbox is ignored",()=>{
  const test=mounted();const {view}=test;
  try {
    const pos=vi.spyOn(view,"posAtDOM");
    pos.mockReturnValueOnce(view.state.doc.content.size);
    fireEvent.click(view.dom.querySelector(".document-checkbox")!);
    pos.mockReturnValueOnce(4);fireEvent.click(view.dom.querySelector(".document-checkbox")!);
    expect(view.state.doc.nodeAt(2)!.attrs.checked).toBe(false);expect(test.change).not.toHaveBeenCalled();
  }finally{test.close();}
});

test("drawn boxes reject detached holders and invalid model targets",()=>{
  const presentation={locked:{drawing:{shapes:[{placement:"inline",width:10,height:10,fill:"#ffffff"}]}}} as SourcePresentation;
  const test=mounted(doc([{type:"lockedInline",attrs:{id:"drawing",label:""}}]),presentation);
  const {view}=test;
  try {
    const holder=view.dom.querySelector<HTMLElement>("[data-locked]")!;
    const shape=holder.querySelector<HTMLElement>(".document-shape")!;
    holder.removeAttribute("data-locked");fireEvent.click(shape);expect(test.change).not.toHaveBeenCalled();
    holder.dataset.locked="drawing";
    const pos=vi.spyOn(view,"posAtDOM");pos.mockReturnValueOnce(view.state.doc.content.size);fireEvent.click(shape);
    pos.mockReturnValueOnce(1);fireEvent.click(shape);expect(test.change).not.toHaveBeenCalled();
    delete shape.dataset.fill;fireEvent.click(shape);
    expect(view.state.doc.nodeAt(2)!.attrs.shapes).toEqual({"0":"#595959"});
  }finally{test.close();}
});

test("a malformed persisted review type is ignored when validating field values",()=>{
  const document=doc([{type:"field",attrs:{id:"field",key:"key",label:"Field"},content:[{type:"text",text:"Text"}]}]);
  const model=schema.nodeFromJSON(document);
  const malformed=model.type.create({...model.attrs,review:{sourceVersion:null,items:[{type:"unknown",id:"review",location:{kind:"control",id:"field"}}]}},model.content);
  const test=mounted(malformed.toJSON());
  try{expect(test.editor.exportSnapshot().fieldValuesValid).toBe(true);expect(test.update.mock.lastCall![0].fields[0].type).toBe("text");}finally{test.close();}
});

test("editable input and paste handlers fall through outside fields while read-only paste is consumed",()=>{
  const test=mounted();const {view}=test;
  try{
    const before=new InputEvent("beforeinput",{bubbles:true,cancelable:true,inputType:"insertText",data:"x"});fireEvent(view.dom,before);expect(before.defaultPrevented).toBe(false);
    const paste=new Event("paste") as ClipboardEvent;Object.defineProperty(paste,"clipboardData",{value:{getData:()=>"Pasted"}});
    let handled=false;view.someProp("handlePaste",fn=>{handled=!!fn(view,paste,view.state.doc.slice(0));return true;});expect(handled).toBe(false);
    test.deny();view.someProp("handlePaste",fn=>{handled=!!fn(view,paste,view.state.doc.slice(0));return true;});expect(handled).toBe(true);
  }finally{test.close();}
});

test("composition without linked or review changes settles without another document mutation",()=>{
  const test=mounted(doc([{type:"text",text:"Original"}]));const {view}=test;
  try{
    fireEvent(view.dom,new CompositionEvent("compositionstart",{bubbles:true}));
    view.dispatch(view.state.tr.insertText("Updated",2,10));
    const count=test.change.mock.calls.length;
    fireEvent(view.dom,new CompositionEvent("compositionstart",{bubbles:true}));
    expect(view.state.doc.textContent).toBe("Updated");expect(test.change).toHaveBeenCalledTimes(count);
  }finally{test.close();}
});

test("composition synchronization also handles programmatic changes without native composition metadata",()=>{
  const field=(id:string)=>({type:"field",attrs:{id,key:"shared",label:"Name"},content:[{type:"text",text:"Old"}]});
  const test=mounted(doc([field("one"),{type:"text",text:" "},field("two")]));const {view}=test;
  try{
    fireEvent(view.dom,new CompositionEvent("compositionstart",{bubbles:true}));view.dispatch(view.state.tr.insertText("New",3,6));
    fireEvent(view.dom,new CompositionEvent("compositionstart",{bubbles:true}));
    expect(view.state.doc.textContent).toBe("New New");
  }finally{test.close();}
});

test("discovery cannot attach to content edited since opening",()=>{
  const test=mounted();try{
    test.view.dispatch(test.view.state.tr.insertText("Changed",4));
    expect(test.editor.attachDiscovery({schema_version:1,source_version_id:"v1",candidates:[],occurrences:[],decisions:[]} as Parameters<typeof test.editor.attachDiscovery>[0],"v1")).toBe(false);
  }finally{test.close();}
});

test("a shape-class holder itself is not treated as a child drawing",()=>{
  const presentation={locked:{drawing:{shapes:[{placement:"inline",width:10,height:10,fill:"#ffffff"}]}}} as SourcePresentation;
  const test=mounted(doc([{type:"lockedInline",attrs:{id:"drawing",label:""}}]),presentation);
  try{const holder=test.view.dom.querySelector("[data-locked]")!;holder.classList.add("document-shape");fireEvent.click(holder);expect(test.change).not.toHaveBeenCalled();}
  finally{test.close();}
});

test("drawn shapes in unsupported blocks receive the accessible checkbox label",()=>{
  const document={type:"doc",content:[{type:"section",attrs:{part:"word/document.xml"},content:[{type:"lockedBlock",attrs:{id:"drawing",label:""}}]}]};
  const presentation={locked:{drawing:{shapes:[{placement:"inline",width:10,height:10,fill:"#ffffff"}]}}} as SourcePresentation;
  const test=mounted(document,presentation);try{test.editor.setShapeCheckboxLabel("Drawn box");expect(test.host.querySelector('[role="checkbox"]')).toHaveAttribute("aria-label","Drawn box");}finally{test.close();}
});
