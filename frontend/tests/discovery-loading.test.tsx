import { act, renderHook } from "@testing-library/react";
import type { components } from "../generated/api";
import { useDiscovery } from "../src/workspace/useDiscovery";
import generated from "../prototype/fields.json";

const version = generated.source_version_id;
const resource = { id: "owned-document", current_version_id: version } as components["schemas"]["ResourceInfo"];
const response = (status: string, source = version, snapshot: object | null = generated) => Response.json({ status, source_version_id: source, snapshot });
const error = () => Response.json({ error: { code: "dependencies_unavailable" } }, { status: 503 });
async function flush() { await act(async () => { await new Promise(resolve => setImmediate(resolve)); }); }
beforeEach(() => vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }));
afterEach(() => vi.useRealTimers());

test("owned current-version results poll to completion and stop; inactive workspace never loads", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response("queued")).mockResolvedValueOnce(response("running")).mockResolvedValueOnce(response("succeeded"));
  vi.stubGlobal("fetch", fetcher);
  const view = renderHook(({ item }) => useDiscovery(item, "csrf"), { initialProps: { item: null as typeof resource | null } });
  await flush(); expect(fetcher).not.toHaveBeenCalled();
  view.rerender({ item: resource }); await flush();
  expect(view.result.current.status).toBe("queued");
  expect((fetcher.mock.calls[0][0] as Request).url).toContain("/api/documents/owned-document/fields");
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(view.result.current.status).toBe("running");
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(view.result.current.snapshot).toEqual(generated);
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(fetcher).toHaveBeenCalledTimes(3);
});

test("network/API/processing errors retry explicitly with CSRF and stale results never attach", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(error())
    .mockResolvedValueOnce(response("not_started")).mockResolvedValueOnce(error())
    .mockResolvedValueOnce(response("queued")).mockResolvedValueOnce(response("failed"))
    .mockResolvedValueOnce(response("succeeded", version, null)).mockResolvedValueOnce(response("succeeded", "new-version"));
  vi.stubGlobal("fetch", fetcher);
  const view = renderHook(() => useDiscovery(resource, "csrf")); await flush();
  expect(view.result.current.error).toBe("internal_error");
  act(() => view.result.current.reload()); await flush();
  expect(view.result.current.error).toBe("dependencies_unavailable");
  act(() => view.result.current.reload()); await flush();
  expect(view.result.current.status).toBe("not_started");
  act(() => view.result.current.reload(true)); await flush();
  expect(view.result.current.error).toBe("dependencies_unavailable");
  act(() => view.result.current.reload(true)); await flush();
  expect(view.result.current.status).toBe("failed");
  for (const index of [3, 4]) {
    const request = fetcher.mock.calls[index][0] as Request;
    expect(request.method).toBe("POST"); expect(request.headers.get("X-CSRF-Token")).toBe("csrf");
  }
  act(() => view.result.current.reload()); await flush();
  expect(view.result.current.error).toBe("internal_error");
  act(() => view.result.current.reload()); await flush();
  expect(view.result.current.status).toBe("stale"); expect(view.result.current.snapshot).toBeNull();
});

test("pending polling is bounded and explicit refresh resumes it", async () => {
  const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response("queued")));
  vi.stubGlobal("fetch", fetcher);
  const view = renderHook(() => useDiscovery(resource, "csrf")); await flush();
  await act(async () => { await vi.advanceTimersByTimeAsync(2000 * 60); });
  expect(fetcher).toHaveBeenCalledTimes(60); expect(view.result.current.paused).toBe(true);
  act(() => view.result.current.reload()); await flush();
  expect(fetcher).toHaveBeenCalledTimes(61); expect(view.result.current.paused).toBe(false);
  view.unmount(); await vi.advanceTimersByTimeAsync(10000); expect(fetcher).toHaveBeenCalledTimes(61);
});

test.each([false, true])("unmount aborts late response/rejection without further polling (%s)", async fail => {
  let finish!: (value: Response) => void, reject!: (value: Error) => void;
  const fetcher = vi.fn().mockImplementation(() => new Promise<Response>((resolve, error) => { finish = resolve; reject = error; }));
  vi.stubGlobal("fetch", fetcher);
  const view = renderHook(() => useDiscovery(resource, "csrf")); await flush(); view.unmount();
  expect((fetcher.mock.calls[0][0] as Request).signal.aborted).toBe(true);
  await act(async () => { if (fail) reject(new Error("late")); else finish(response("succeeded")); });
  await vi.advanceTimersByTimeAsync(5000); expect(fetcher).toHaveBeenCalledTimes(1);
});

test("an aborted start cannot load results or repeat the POST on a token change", async () => {
  let finish!: (value: Response) => void;
  const fetcher = vi.fn().mockResolvedValueOnce(response("not_started"))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }))
    .mockResolvedValueOnce(response("succeeded"));
  vi.stubGlobal("fetch", fetcher);
  const view = renderHook(({ token }) => useDiscovery(resource, token), { initialProps: { token: "csrf" } }); await flush();
  act(() => view.result.current.reload(true)); await flush();
  view.rerender({ token: "rotated" }); await flush();
  await act(async () => finish(response("queued")));
  expect(fetcher).toHaveBeenCalledTimes(3);
  expect((fetcher.mock.calls[2][0] as Request).method).toBe("GET");
  expect(view.result.current.status).toBe("succeeded");
});
