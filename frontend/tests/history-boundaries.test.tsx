import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HistoryPanel } from "../src/workspace/HistoryPanel";
import { setLanguage } from "../src/i18n";
const version={id:"v1",number:1,created_at:"2026-09-01T12:00:00Z",size_bytes:1,digest:"hash",unsupported_count:0,is_current:true,parent_version_id:null,restored_from_version_id:null,restored_from_number:null};
const page={items:[version],current_version_id:"v1",retention:{keep_latest:null,revision:0},next_before:2};
const document={type:"doc",content:[{type:"section",attrs:{part:"word/document.xml"},content:[{type:"paragraph",attrs:{id:"p"},content:[{type:"text",text:"History"}]}]}]};
const props={identity:"document",current:"v1",filename:"Document.docx",dirty:false,blocked:false,busy:false,onRestore:vi.fn(),onReopen:vi.fn()};
beforeEach(async()=>setLanguage("en"));

test("history reports network failures and retries previews while retaining version pagination",async()=>{
  let previewCalls=0;
  const fetcher=vi.fn(async(request:Request)=>{
    if(request.url.includes("/content")){if(++previewCalls===1)throw new Error("offline");return Response.json({version,document});}
    return Response.json(new URL(request.url).searchParams.has("before")?{...page,items:[],next_before:null}:page);
  });vi.stubGlobal("fetch",fetcher);
  render(<HistoryPanel {...props}/>);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button",{name:"Retry preview"}));
  await screen.findByRole("textbox",{name:"Read-only historical document"});
  fireEvent.click(screen.getByRole("button",{name:"Show older revisions"}));
  await waitFor(()=>expect(screen.queryByRole("button",{name:"Show older revisions"})).toBeNull());
  expect(fetcher.mock.calls.some(([request])=>new URL(request.url).searchParams.get("before")==="2")).toBe(true);
});

test("history ignores a rejected preview after unmount and renders empty history",async()=>{
  let reject!:(error:Error)=>void;
  vi.stubGlobal("fetch",vi.fn((request:Request)=>request.url.includes("/content")?new Promise<Response>((_,no)=>{reject=no;}):Promise.resolve(Response.json({...page,items:[],next_before:null}))));
  const view=render(<HistoryPanel {...props}/>);
  expect(await screen.findByText("No saved revisions.")).toBeVisible();
  view.unmount();await act(async()=>reject(new Error("cancelled")));
  expect(screen.queryByRole("alert")).toBeNull();
});
