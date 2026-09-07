import { act, renderHook, waitFor } from "@testing-library/react";
import { useVersionHistory } from "../src/workspace/useVersionHistory";

const version = (id: string, number: number) => ({ id, number, is_current: number === 2 });
const page = (items = [version("two", 2)], before: number | null = 2, current = "two") => Response.json({ retention: { keep_latest: null, revision: 0 }, items, next_before: before, current_version_id: current });
const failure = () => Response.json({ error: { code: "not_found" } }, { status: 404 });

test("history pages are bounded, deduplicated and show a consistent current marker after concurrent saves", async () => {
  const fetcher = vi.fn<(request: Request) => Promise<Response>>().mockResolvedValueOnce(page()).mockResolvedValueOnce(page([version("two", 2), version("one", 1)], null, "three"));
  vi.stubGlobal("fetch", fetcher);
  const state = renderHook(() => useVersionHistory("document"));
  await waitFor(() => expect(state.result.current.page?.items).toHaveLength(1));
  expect(new URL(fetcher.mock.calls[0][0].url).searchParams.get("limit")).toBe("20");
  await act(() => state.result.current.load(true));
  expect(new URL(fetcher.mock.calls[1][0].url).searchParams.get("before")).toBe("2");
  expect(state.result.current.page?.items.map(item => [item.id, item.is_current])).toEqual([["two", false], ["one", false]]);
  await act(() => state.result.current.load(true)); expect(fetcher).toHaveBeenCalledTimes(2);
  fetcher.mockResolvedValueOnce(page([version("three", 3)], null, "three"));
  await act(() => state.result.current.load());
  expect(state.result.current.page?.items.map(item => item.id)).toEqual(["three"]);
});

test("list errors preserve existing pages and allow explicit retry", async () => {
  const fetcher = vi.fn<(request: Request) => Promise<Response>>().mockResolvedValueOnce(failure()).mockResolvedValueOnce(page()).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(page([], null));
  vi.stubGlobal("fetch", fetcher);
  const state = renderHook(() => useVersionHistory("document"));
  await waitFor(() => expect(state.result.current.error).toBe("not_found"));
  await act(() => state.result.current.load()); expect(state.result.current.error).toBe("");
  await act(() => state.result.current.load(true));
  expect(state.result.current.error).toBe("internal_error"); expect(state.result.current.page?.items).toHaveLength(1);
  await act(() => state.result.current.load()); expect(state.result.current.page?.items).toHaveLength(0);
});

test.each(["resolve", "reject"])("a replaced request ignores its late %s and unmount aborts loading", async phase => {
  let finish!: (value: Response) => void, fail!: (error: Error) => void;
  const fetcher = vi.fn<(request: Request) => Promise<Response>>().mockImplementationOnce(() => new Promise((resolve, reject) => { finish = resolve; fail = reject; })).mockResolvedValueOnce(page());
  vi.stubGlobal("fetch", fetcher);
  const state = renderHook(() => useVersionHistory("document"));
  await act(() => state.result.current.load(true)); expect(fetcher).toHaveBeenCalledTimes(1);
  await act(() => state.result.current.load());
  await act(async () => { if (phase === "resolve") finish(page([], null)); else fail(new Error("old")); });
  expect(state.result.current.page?.items).toHaveLength(1); expect(state.result.current.error).toBe("");
  expect(fetcher.mock.calls[0][0].signal.aborted).toBe(true);
  state.unmount(); expect(fetcher.mock.calls[1][0].signal.aborted).toBe(true);
});
