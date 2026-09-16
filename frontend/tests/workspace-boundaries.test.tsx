import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps } from "react";
import { Workspace } from "../src/workspace/Workspace";
import type { DocumentEditor } from "../src/editor/DocumentEditor";
import type { WorkspaceSettings } from "../src/workspace/WorkspaceSettings";
import type { HistoryPanel } from "../src/workspace/HistoryPanel";
import type { useDocumentSave } from "../src/workspace/useDocumentSave";
import type { useRestore } from "../src/workspace/useRestore";
import type { useAutosave } from "../src/workspace/useAutosave";
import { setLanguage } from "../src/i18n";
import type { Resource } from "../src/library/useLibrary";

const fixture=vi.hoisted(()=>({
  editor:null as unknown as ComponentProps<typeof DocumentEditor>,settings:null as unknown as ComponentProps<typeof WorkspaceSettings>,history:null as unknown as ComponentProps<typeof HistoryPanel>,
  saveOptions:null as unknown as Parameters<typeof useDocumentSave>[0],restoreOptions:null as unknown as Parameters<typeof useRestore>[0],autosave:null as unknown as Parameters<typeof useAutosave>[0],
  saving:{busy:false,pending:false,conflict:false,error:"",acknowledged:0,reviewSaved:false,save:vi.fn(async()=>"clean"),reset:vi.fn()},
  restoring:{busy:false,pending:null as null|Parameters<ComponentProps<typeof HistoryPanel>["onRestore"]>[0],conflict:false,error:"",restore:vi.fn(),reset:vi.fn()},
  access:{status:"active",error:"",canEdit:()=>true,credentials:vi.fn(()=>({client_id:"client",lease_id:"lease",source_version_id:"v1"})),retry:vi.fn(),invalidate:vi.fn()},
  discovery:{status:"complete",error:"",paused:false,busy:false,snapshot:null,reload:vi.fn()},
}));
vi.mock("../src/editor/DocumentEditor",()=>({DocumentEditor:(props:ComponentProps<typeof DocumentEditor>)=>{fixture.editor=props;return <p>Editor fixture</p>;}}));
vi.mock("../src/workspace/WorkspaceSettings",()=>({WorkspaceSettings:(props:ComponentProps<typeof WorkspaceSettings>)=>{fixture.settings=props;return null;}}));
vi.mock("../src/workspace/HistoryPanel",()=>({HistoryPanel:(props:ComponentProps<typeof HistoryPanel>)=>{fixture.history=props;return <p>History fixture</p>;}}));
vi.mock("../src/workspace/useDocumentSave",()=>({useDocumentSave:(props:Parameters<typeof useDocumentSave>[0])=>{fixture.saveOptions=props;return fixture.saving;}}));
vi.mock("../src/workspace/useRestore",()=>({useRestore:(props:Parameters<typeof useRestore>[0])=>{fixture.restoreOptions=props;return fixture.restoring;}}));
vi.mock("../src/workspace/useAutosave",()=>({useAutosave:(props:Parameters<typeof useAutosave>[0])=>{fixture.autosave=props;}}));
vi.mock("../src/workspace/useEditingLease",()=>({useEditingLease:()=>fixture.access}));
vi.mock("../src/workspace/useDiscovery",()=>({useDiscovery:()=>fixture.discovery}));
const resource={id:"id",kind:"template",title:"Template",current_version_id:"v1",original_filename:"File.docx"} as Resource;
const content={resource,document:{type:"doc",content:[]}};
const version={id:"old",number:1,created_at:"2026-09-01",size_bytes:1,digest:"hash",unsupported_count:0,is_current:false,parent_version_id:null,restored_from_version_id:null,restored_from_number:null};
const props={identity:"id",csrfToken:"csrf",dirty:false,onDirty:vi.fn()};
const snapshot={document:content.document,revision:1,fieldValuesValid:true,composing:false};
function mount(){const view=render(<Workspace {...props}/>);return {...view,refresh:()=>view.rerender(<Workspace {...props}/>)};}
async function ready(){await screen.findByText("Editor fixture");}
beforeEach(async()=>{
  await setLanguage("en");
  Object.assign(fixture.saving,{busy:false,pending:false,conflict:false,error:"",acknowledged:0});fixture.saving.save.mockReset().mockResolvedValue("clean");fixture.saving.reset.mockClear();
  Object.assign(fixture.restoring,{busy:false,pending:null,conflict:false,error:""});fixture.restoring.restore.mockClear();fixture.restoring.reset.mockClear();
  Object.assign(fixture.access,{status:"active",error:""});Object.assign(fixture.discovery,{status:"complete",error:"",paused:false});
  fixture.discovery.reload.mockClear();
  vi.stubGlobal("fetch",vi.fn().mockResolvedValue(Response.json(content)));
});

test("autosave requires a valid settled editor snapshot and disabled autosave is explained",async()=>{
  mount();await ready();expect(fixture.saveOptions.read()).toBeNull();
  act(()=>fixture.autosave.save());expect(fixture.saving.save).not.toHaveBeenCalled();
  act(()=>fixture.editor.onReader?.(()=>({...snapshot,composing:true})));act(()=>fixture.autosave.save());expect(fixture.saving.save).not.toHaveBeenCalled();
  act(()=>fixture.editor.onReader?.(()=>snapshot));act(()=>fixture.autosave.save());expect(fixture.saving.save).toHaveBeenCalledOnce();
  act(()=>fixture.settings.onAutosave?.(false));expect(screen.getByText("Autosave is off. Use Save document to keep your changes.")).toBeVisible();
});

test("late saved and renamed notifications cannot resurrect content after reopening",async()=>{
  const view=mount();await ready();
  fixture.access.status="paused";fixture.access.error="revision";view.refresh();
  vi.stubGlobal("fetch",vi.fn(()=>new Promise(()=>{})));
  const rename=fixture.settings.onResource;
  fireEvent.click(screen.getByRole("button",{name:"Reopen saved document"}));
  act(()=>fixture.saveOptions.onSaved(resource));act(()=>rename(resource));
  expect(screen.queryByText("Editor fixture")).toBeNull();
});

test("reopen waits for mutations and prompts before discarding a pending restore",async()=>{
  const view=mount();await ready();fixture.discovery.status="stale";fixture.saving.busy=true;view.refresh();
  fireEvent.click(screen.getByRole("button",{name:"Reopen saved document"}));expect(fixture.saving.reset).not.toHaveBeenCalled();
  fixture.saving.busy=false;fixture.restoring.pending=version;view.refresh();
  const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);
  fireEvent.click(screen.getByRole("button",{name:"Reopen saved document"}));expect(confirm).toHaveBeenCalled();expect(fixture.saving.reset).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);fireEvent.click(screen.getByRole("button",{name:"Reopen saved document"}));expect(fixture.saving.reset).toHaveBeenCalledOnce();
});

test("restore rejects mutations and composition, and lease errors stay visible",async()=>{
  const view=mount();await ready();fireEvent.click(screen.getByRole("button",{name:"Version history"}));
  fixture.saving.pending=true;view.refresh();act(()=>fixture.history.onRestore(version));expect(fixture.restoring.restore).not.toHaveBeenCalled();
  fixture.saving.pending=false;act(()=>fixture.editor.onCompositionChange?.(true));act(()=>fixture.history.onRestore(version));expect(fixture.restoring.restore).not.toHaveBeenCalled();
  act(()=>fixture.editor.onCompositionChange?.(false));act(()=>fixture.history.onRestore(version));expect(fixture.restoring.restore).toHaveBeenCalledWith(version);
  fixture.access.status="paused";fixture.access.error="internal_error";fixture.restoring.error="lease_lost";view.refresh();
  expect(screen.getAllByRole("alert")).toHaveLength(2);
});

test("copy without a fields reader uses its title and handles missing saved versions",async()=>{
  mount();await ready();fireEvent.click(screen.getByRole("button",{name:"Save to documents"}));
  expect(screen.getByRole("textbox")).toHaveValue("Template");
  act(()=>fixture.saveOptions.onSaved({...resource,current_version_id:""}));
  fireEvent.submit(screen.getByRole("textbox").closest("form")!);
  await waitFor(()=>expect(fixture.saving.save).toHaveBeenCalled());
  expect(vi.mocked(fetch).mock.calls).toHaveLength(1);
});

test.each(["resolve","reject"] as const)("copy ignores late %s after unmount",async outcome=>{
  let resolve!:(response:Response)=>void,reject!:(error:Error)=>void;
  const fetcher=vi.fn().mockResolvedValueOnce(Response.json(content)).mockImplementationOnce(()=>new Promise<Response>((yes,no)=>{resolve=yes;reject=no;}));vi.stubGlobal("fetch",fetcher);
  const view=mount();await ready();fireEvent.click(screen.getByRole("button",{name:"Save to documents"}));fireEvent.submit(screen.getByRole("textbox").closest("form")!);
  await waitFor(()=>expect(fetcher).toHaveBeenCalledTimes(2));view.unmount();
  await act(async()=>outcome==="resolve"?resolve(Response.json(resource)):reject(new Error("cancelled")));
  expect(screen.queryByRole("alert")).toBeNull();
});

test("copy server and network errors preserve the prompt for retry",async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce(Response.json(content)).mockResolvedValueOnce(Response.json({error:{code:"internal_error"}},{status:503})).mockRejectedValueOnce(new Error("offline"));vi.stubGlobal("fetch",fetcher);
  mount();await ready();fireEvent.click(screen.getByRole("button",{name:"Save to documents"}));
  for(let i=0;i<2;i++){fireEvent.submit(screen.getByRole("textbox").closest("form")!);await screen.findByRole("alert");}
  expect(fetcher).toHaveBeenCalledTimes(3);
});

test("a rejected workspace load after unmount has no effect",async()=>{
  let reject!:(error:Error)=>void;vi.stubGlobal("fetch",vi.fn(()=>new Promise<Response>((_,no)=>{reject=no;})));
  const view=mount();view.unmount();await act(async()=>reject(new Error("cancelled")));expect(screen.queryByRole("alert")).toBeNull();
});

test("paused discovery offers a refresh without discarding the editor",async()=>{
  fixture.discovery.paused=true;mount();await ready();fireEvent.click(screen.getByRole("button",{name:"Retry status check"}));expect(fixture.discovery.reload).toHaveBeenCalledOnce();expect(screen.getByText("Editor fixture")).toBeVisible();
});
