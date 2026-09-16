import { EditorState, TextSelection } from "prosemirror-state";
import { editorSchema as schema, fields } from "../src/editor/model";
import { paragraphIdentities, retainComposedField, suggestFieldLabel } from "../src/editor/transactions";
const paragraph=(text:string,id:string|null)=>schema.nodes.paragraph.create({id},text?schema.text(text):[]);
const state=(nodes:ReturnType<typeof paragraph>[])=>EditorState.create({doc:schema.nodes.doc.create(null,schema.nodes.section.create({part:"word/document.xml"},nodes))});

test("paragraph identity assignment handles missing origins and descendants of newly created paragraphs",()=>{
  const original=state([paragraph("No origin",null),paragraph("First","new:source:old"),paragraph("Duplicate","new:source:old"),paragraph("Missing",null)]);
  const tr=paragraphIdentities(original.tr.insertText("!",2));
  const ids:string[]=[];tr.doc.descendants(node=>{if(node.type.name==="paragraph")ids.push(node.attrs.id);});
  expect(ids[0]).toBeNull();expect(ids[1]).toBe("new:source:old");
  expect(ids[2]).toMatch(/^new:source:[0-9a-f]{32}$/);expect(ids[3]).toMatch(/^new:source:[0-9a-f]{32}$/);expect(ids[2]).not.toBe(ids[3]);
});

test.each([false,true])("restoring an unwrapped field preserves authored replacement marks (empty original: %s)",empty=>{
  const mark=schema.marks.source.create({id:"replacement",bold:true});
  const field=schema.nodes.field.create({id:"field",key:"key",label:"Name"},empty?[]:schema.text("Old"));
  let source=state([schema.nodes.paragraph.create({id:"p"},field)]);
  source=source.apply(source.tr.setSelection(TextSelection.create(source.doc,3,empty?3:6)));
  const replacement=source.tr.replaceWith(2,2+field.nodeSize,schema.text("New",empty?[]:[mark]));
  const result=retainComposedField(source,replacement,replacement.mapping);
  expect(fields(result.doc)).toMatchObject([{id:"field",value:"New"}]);
  expect(result.doc.nodeAt(3)!.marks).toEqual(empty?[]:[mark]);
});

test("field label suggestions reject control characters in preceding source text",()=>{
  let current=state([paragraph("\u0000 Name: ____","p")]);
  current=current.apply(current.tr.setSelection(TextSelection.create(current.doc,10,14)));
  expect(suggestFieldLabel(current)).toBe("");
});
