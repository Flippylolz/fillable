import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { sourceRules } from "../src/editor/SourceLayout";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { i18n } from "../src/i18n";
import corpus from "../prototype/document.json";

test("source CSS is scoped, bounded and cannot load URLs or inject selectors", () => {
  expect(sourceRules("one", null)).toBe("");
  const css = sourceRules("one", { section: { width: "595pt", background: "url(https://evil)", position: "fixed" }, nodes: {
    'word/document.xml:10': { "font-family": '"Times New Roman"', "font-size": "11.5pt", color: "#000000", width: "1pt;} body {display:none" },
    'evil"] body': { width: "100pt" }, bad: null,
  } });
  expect(css).toContain('[data-layout="one"]');
  expect(css).toContain('font-family:"Times New Roman"!important');
  expect(css).toContain('font-size:11.5pt!important');
  expect(css).toContain('[data-source^="new:word/document.xml:10:"]');
  expect(css).not.toMatch(/evil|url\(|position|display:none/);
  expect(sourceRules("empty", {})).toContain('section[data-part="word/document.xml"]');
});

test("presentation updates do not remount or mutate the editable document", () => {
  const snapshot = vi.fn(), reader = vi.fn();
  const ui = (width: string) => <I18nextProvider i18n={i18n}><DocumentEditor initialDocument={corpus} onSnapshot={snapshot} onReader={reader} sourcePresentation={{ section: { width }, nodes: {} }} /></I18nextProvider>;
  const view = render(ui("595pt"));
  const editor = view.container.querySelector(".ProseMirror");
  const before = reader.mock.calls[0][0]().document;
  view.rerender(ui("600pt"));
  expect(view.container.querySelector(".ProseMirror")).toBe(editor);
  expect(reader.mock.calls[0][0]().document).toEqual(before);
  expect(snapshot).not.toHaveBeenCalled();
  expect(view.container.querySelector("style")!.textContent).toContain("600pt");
  expect(screen.getByRole("textbox", {name: /Редагований документ|Editable document/})).toBe(editor);
});

test("unsupported source graphics show bounded shapes without exposing internal XML numbers", async () => {
  const { sourceNodeView } = await import("../src/editor/sourceNodes");
  const { editorSchema } = await import("../src/editor/model");
  const node = editorSchema.nodes.lockedInline.create({id:"drawing",label:"12700025400"});
  const view = sourceNodeView({locked:{ drawing:{text:"",shapes:[
    {x:10,y:20,width:12,height:12,fill:"#ffffff"},
    {x:Infinity,y:0,width:12,height:12,fill:"#ffffff"},
    {x:1,y:0,width:12,height:12,fill:"url(evil)"},
  ]}}})(node);
  expect(view.dom.textContent).toBe("");
  expect((view.dom as HTMLElement).querySelectorAll("span")).toHaveLength(1);
  expect((view.dom as HTMLElement).querySelector("span")!.style.left).toBe("10pt");
  expect(view.ignoreMutation!({type:"selection",target:view.dom})).toBe(true);
  expect(sourceNodeView(undefined)(node).dom.textContent).toBe("12700025400");
});
