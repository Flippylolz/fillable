import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { SessionPages } from "../src/SessionPages";
import type { Library } from "../src/library/Library";
import type { Workspace } from "../src/workspace/Workspace";
import { setLanguage } from "../src/i18n";

vi.mock("../src/library/Library",()=>({Library:({onDirty,onOpen}:ComponentProps<typeof Library>)=><><button onClick={()=>onDirty(true)}>Dirty upload</button><button onClick={()=>onOpen?.("11111111-1111-4111-8111-111111111111")}>Open fixture</button></>}));
vi.mock("../src/workspace/Workspace",()=>({Workspace:({onDirty,onOpenResource}:ComponentProps<typeof Workspace>)=><><button onClick={()=>onDirty(true)}>Dirty document</button><button onClick={()=>onOpenResource?.("22222222-2222-4222-8222-222222222222")}>Open copy</button></>}));
vi.mock("../src/accounts/Profile",()=>({Profile:()=>null}));
const session={csrf_token:"csrf",user:{id:"owner",login:"owner",display_name:"Owner",role:"user" as const,ui_language:"en" as const}};
const props={session,accept:vi.fn(),authBusy:false,setAuthBusy:vi.fn(),logout:vi.fn(),connection:"ok" as const,onRetry:vi.fn()};
beforeEach(async()=>{await setLanguage("en");window.history.replaceState(null,"","/documents");vi.stubGlobal("fetch",vi.fn().mockResolvedValue(Response.json({used_bytes:0,limit_bytes:10,reserved_bytes:0,available_bytes:10,over_limit:false})));});

test("history canonicalizes unknown paths and modified links retain native navigation",async()=>{
  const view=render(<SessionPages {...props}/>);
  await act(async()=>{});
  window.history.pushState(null,"","/unknown");fireEvent.popState(window);
  expect(window.location.pathname).toBe("/documents");
  const link=screen.getByRole("link",{name:"Profile"});
  const click=new MouseEvent("click",{bubbles:true,cancelable:true,ctrlKey:true});fireEvent(link,click);
  expect(click.defaultPrevented).toBe(false);expect(window.location.pathname).toBe("/documents");
  fireEvent.click(link);expect(window.location.pathname).toBe("/profile");
  fireEvent.click(view.container.querySelector(".shell-brand-compact")!);expect(window.location.pathname).toBe("/documents");
});

test("dirty uploads protect closing the tab and clear the leave guard on unmount",async()=>{
  let guard=()=>true;const setLeaveGuard=vi.fn((value:()=>boolean)=>{guard=value;});
  const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);
  const view=render(<SessionPages {...props} setLeaveGuard={setLeaveGuard}/>);await act(async()=>{});
  expect(guard()).toBe(true);fireEvent.click(screen.getByText("Dirty upload"));
  const event=new Event("beforeunload",{cancelable:true});fireEvent(window,event);expect(event.defaultPrevented).toBe(true);
  expect(guard()).toBe(false);expect(confirm).toHaveBeenCalledOnce();
  view.unmount();expect(guard()).toBe(true);
});

test("switching from a dirty document requires consent and mobile navigation closes",async()=>{
  const confirm=vi.spyOn(window,"confirm").mockReturnValue(false);
  const view=render(<SessionPages {...props}/>);await act(async()=>{});
  fireEvent.click(screen.getByText("Open fixture"));fireEvent.click(screen.getByText("Dirty document"));
  fireEvent.click(screen.getByText("Open copy"));expect(window.location.pathname).toContain("11111111");
  confirm.mockReturnValue(true);fireEvent.click(screen.getByText("Open copy"));expect(window.location.pathname).toContain("22222222");
  fireEvent.click(view.container.querySelector(".shell-menu")!);expect(view.container.querySelector(".app-sidebar-open")).not.toBeNull();
  fireEvent.keyDown(window,{key:"Tab"});expect(view.container.querySelector(".app-sidebar-open")).not.toBeNull();
  fireEvent.click(view.container.querySelector(".shell-brand")!);expect(view.container.querySelector(".app-sidebar-open")).toBeNull();
  expect(window.location.pathname).toBe("/documents");
  fireEvent.click(screen.getByRole("link",{name:"Document workspace"}));expect(window.location.pathname).toContain("22222222");
});

test("anonymous sessions produce no application shell",()=>{
  const view=render(<SessionPages {...props} session={{user:null,csrf_token:"anonymous"}}/>);
  expect(view.container).toBeEmptyDOMElement();
});
