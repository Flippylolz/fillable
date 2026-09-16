import { act, renderHook, waitFor } from "@testing-library/react";
import { useLibrary } from "../src/library/useLibrary";
import { useStorageUsage } from "../src/shell/useStorageUsage";

function pending() {
  let resolve!: (value: Response) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<Response>((yes, no) => { resolve=yes; reject=no; });
  return { promise, resolve, reject };
}
const item = { id: "one", title: "First" };

test("storage usage exposes server and network errors, and ignores superseded responses", async () => {
  const first=pending();
  vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(first.promise)
    .mockResolvedValueOnce(Response.json({error:{code:"storage_unavailable"}},{status:503}))
    .mockRejectedValueOnce(new Error("offline")));
  const hook=renderHook(({revision})=>useStorageUsage(revision),{initialProps:{revision:0}});
  hook.rerender({revision:1});
  await waitFor(()=>expect(hook.result.current.error).toBe("storage_unavailable"));
  await act(async()=>first.resolve(Response.json({used_bytes:99})));
  expect(hook.result.current.usage).toBeNull();
  hook.rerender({revision:2});
  await waitFor(()=>expect(hook.result.current.error).toBe("internal_error"));
});

test("storage usage ignores a network rejection after unmount", async () => {
  const request=pending(); vi.stubGlobal("fetch",vi.fn(()=>request.promise));
  const hook=renderHook(()=>useStorageUsage(0)); hook.unmount();
  await act(async()=>request.reject(new Error("cancelled")));
  expect(hook.result.current).toEqual({usage:null,error:""});
});

test("library does not paginate before loading or without a cursor and reports load failures", async () => {
  const first=pending(); const fetcher=vi.fn().mockReturnValueOnce(first.promise).mockRejectedValueOnce(new Error("offline"));
  vi.stubGlobal("fetch",fetcher);
  const hook=renderHook(({revision})=>useLibrary("template",revision),{initialProps:{revision:0}});
  await act(async()=>hook.result.current.loadMore()); expect(fetcher).toHaveBeenCalledTimes(1);
  await act(async()=>first.resolve(Response.json({items:[item]})));
  await act(async()=>hook.result.current.loadMore()); expect(fetcher).toHaveBeenCalledTimes(1);
  expect(hook.result.current.items).toEqual([item]);
  hook.rerender({revision:1});
  await waitFor(()=>expect(hook.result.current.error).toBe("internal_error"));
  expect(hook.result.current.loading).toBe(false);
});

test.each(["resolve","reject"] as const)("library ignores %s of initial requests after unmount",async outcome=>{
  const request=pending();vi.stubGlobal("fetch",vi.fn(()=>request.promise));
  const hook=renderHook(()=>useLibrary("document",0));hook.unmount();
  await act(async()=>outcome==="resolve"?request.resolve(Response.json({items:[item]})):request.reject(new Error("cancelled")));
  expect(hook.result.current.items).toEqual([]); expect(hook.result.current.error).toBe("");
});

test.each(["resolve","reject"] as const)("library ignores %s of stale pagination and prevents a concurrent page request", async outcome=>{
  const page=pending();const fetcher=vi.fn().mockResolvedValueOnce(Response.json({items:[item],next_cursor:"next"})).mockReturnValueOnce(page.promise).mockResolvedValueOnce(Response.json({items:[]}));
  vi.stubGlobal("fetch",fetcher);
  const hook=renderHook(({revision})=>useLibrary("document",revision),{initialProps:{revision:0}});
  await waitFor(()=>expect(hook.result.current.loading).toBe(false));
  let loading!:Promise<void>;act(()=>{loading=hook.result.current.loadMore();});
  await act(async()=>hook.result.current.loadMore());expect(fetcher).toHaveBeenCalledTimes(2);
  hook.rerender({revision:1});
  await waitFor(()=>expect(hook.result.current.loading).toBe(false));
  await act(async()=>{if(outcome==="resolve")page.resolve(Response.json({items:[item]}));else page.reject(new Error("cancelled"));await loading;});
  expect(hook.result.current.items).toEqual([]);expect(hook.result.current.error).toBe("");expect(hook.result.current.more).toBe(false);
});
