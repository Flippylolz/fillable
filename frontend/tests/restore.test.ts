import { act, renderHook } from "@testing-library/react";
import type { components } from "../generated/api";
import { useRestore } from "../src/workspace/useRestore";

const v1 = "11111111-1111-4111-8111-111111111111", v2 = "22222222-2222-4222-8222-222222222222", v3 = "33333333-3333-4333-8333-333333333333";
const selected: components["schemas"]["VersionInfo"] = { id: v1, number: 1, created_at: "2026-09-07T09:00:00Z", size_bytes: 100,
  digest: "digest", unsupported_count: 0, is_current: false, parent_version_id: null, restored_from_version_id: null, restored_from_number: null };
const body = { source_version_id: v2, client_id: v1, lease_id: v2 };
const resource = { id: v1, current_version_id: v3 };
const saved = () => Response.json({ resource, saved_version_id: v3 }, { status: 201 });
const content = () => Response.json({ version: { ...selected, id: v3, is_current: true, restored_from_version_id: v1 }, document: { type: "doc" } });
const failure = (code = "quota_exceeded", status = 409, reason?: string) => Response.json({ error: { code, parameters: { reason } } }, { status });
function setup() {
  const credentials = vi.fn<() => typeof body | undefined>().mockReturnValue(body);
  const onRestored = vi.fn(), onAccessLost = vi.fn();
  const fetcher = vi.fn<(request: Request) => Promise<Response>>().mockImplementation(async request => new URL(request.url).pathname.endsWith("/restore") ? saved() : content());
  vi.stubGlobal("fetch", fetcher);
  const hook = renderHook(() => useRestore({ identity: v1, csrfToken: "csrf", credentials, onRestored, onAccessLost }));
  return { ...hook, fetcher, credentials, onRestored, onAccessLost };
}

test("restore requires a live lease and loads the exact committed pair before adopting", async () => {
  const state = setup();
  state.credentials.mockReturnValueOnce(undefined);
  await act(() => state.result.current.restore(selected));
  expect(state.result.current.error).toBe("lease_lost"); expect(state.fetcher).not.toHaveBeenCalled();
  await act(() => state.result.current.restore(selected));
  expect(state.fetcher.mock.calls[0][0].headers.get("X-CSRF-Token")).toBe("csrf");
  expect(await state.fetcher.mock.calls[0][0].clone().json()).toEqual(body);
  expect(state.onRestored).toHaveBeenCalledWith({ resource, document: { type: "doc" } });
  expect(state.result.current).toMatchObject({ busy: false, pending: null, error: "" });
});

test.each(["network", "internal_error", "operation_in_progress"])("%s keeps the exact request despite changed selection and lost credentials", async kind => {
  const state = setup();
  if (kind === "network") state.fetcher.mockRejectedValueOnce(new Error("offline"));
  else state.fetcher.mockResolvedValueOnce(failure(kind, kind === "internal_error" ? 503 : 409));
  await act(() => state.result.current.restore(selected));
  expect(state.result.current.pending?.id).toBe(v1); expect(state.onRestored).not.toHaveBeenCalled();
  state.credentials.mockReturnValue(undefined);
  await act(() => state.result.current.restore({ ...selected, id: v2, number: 2 }));
  const first = state.fetcher.mock.calls[0][0], retry = state.fetcher.mock.calls[1][0];
  expect(retry.url).toBe(first.url);
  expect(retry.headers.get("Idempotency-Key")).toBe(first.headers.get("Idempotency-Key"));
  expect(await retry.clone().json()).toEqual(await first.clone().json());
  expect(state.onRestored).toHaveBeenCalledTimes(1);
});

test.each(["quota_exceeded", "operation_aborted", "authentication_required", "forbidden", "lease_lost"])("definite %s retains draft and allows a fresh operation", async kind => {
  const state = setup();
  state.fetcher.mockResolvedValueOnce(failure(kind === "lease_lost" ? "operation_conflict" : kind, kind === "authentication_required" ? 401 : 409, kind === "lease_lost" ? kind : undefined));
  await act(() => state.result.current.restore(selected));
  expect(state.result.current.pending).toBeNull(); expect(state.result.current.error).toBe(kind);
  expect(state.onRestored).not.toHaveBeenCalled();
  if (["authentication_required", "forbidden", "lease_lost"].includes(kind)) expect(state.onAccessLost).toHaveBeenCalledWith(kind);
  await act(() => state.result.current.restore(selected));
  expect(state.fetcher.mock.calls[1][0].headers.get("Idempotency-Key")).not.toBe(state.fetcher.mock.calls[0][0].headers.get("Idempotency-Key"));
  expect(state.onRestored).toHaveBeenCalledTimes(1);
});

test.each(["post", "error", "missing_reason", "content_id", "content_current", "content_origin"])("%s revision conflict never replaces draft and needs explicit reset", async kind => {
  const state = setup();
  if (kind === "post") state.fetcher.mockResolvedValueOnce(Response.json({ resource, saved_version_id: v2 }));
  else if (kind === "error" || kind === "missing_reason") state.fetcher.mockResolvedValueOnce(failure("operation_conflict", 409, kind === "error" ? "revision" : undefined));
  else state.fetcher.mockResolvedValueOnce(saved()).mockResolvedValueOnce(Response.json({ version: { ...selected, id: kind === "content_id" ? v2 : v3,
    is_current: kind !== "content_current", restored_from_version_id: kind === "content_origin" ? v2 : v1 }, document: {} }));
  await act(() => state.result.current.restore(selected));
  expect(state.result.current).toMatchObject({ conflict: true, pending: null, error: "revision" });
  expect(state.onRestored).not.toHaveBeenCalled(); expect(state.onAccessLost).toHaveBeenCalledWith("revision");
  const count = state.fetcher.mock.calls.length;
  await act(() => state.result.current.restore(selected)); expect(state.fetcher).toHaveBeenCalledTimes(count);
  act(() => state.result.current.reset());
  await act(() => state.result.current.restore(selected)); expect(state.onRestored).toHaveBeenCalledTimes(1);
});

test.each(["response", "network"])("committed restore with failed %s content load keeps the original retry", async kind => {
  const state = setup();
  state.fetcher.mockResolvedValueOnce(saved());
  if (kind === "network") state.fetcher.mockRejectedValueOnce(new Error("offline"));
  else state.fetcher.mockResolvedValueOnce(failure("not_found", 404));
  await act(() => state.result.current.restore(selected));
  expect(state.result.current).toMatchObject({ error: "restore_load", pending: selected });
  expect(state.onAccessLost).toHaveBeenCalledWith("revision"); expect(state.onRestored).not.toHaveBeenCalled();
  await act(() => state.result.current.restore(selected));
  expect(state.fetcher.mock.calls[2][0].headers.get("Idempotency-Key")).toBe(state.fetcher.mock.calls[0][0].headers.get("Idempotency-Key"));
  expect(state.onRestored).toHaveBeenCalledTimes(1);
});

test("timeout prevents overlap and preserves uncertain attempt", async () => {
  vi.useFakeTimers();
  try {
    const state = setup();
    state.fetcher.mockImplementationOnce(request => new Promise((_resolve, reject) => request.signal.addEventListener("abort", () => reject(new Error("aborted")))));
    let running!: Promise<void>;
    await act(async () => { running = state.result.current.restore(selected); });
    await act(() => state.result.current.restore(selected)); expect(state.fetcher).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(45000); await running; });
    expect(state.result.current).toMatchObject({ busy: false, pending: selected, error: "internal_error" });
  } finally { vi.useRealTimers(); }
});

test.each(["post", "content", "reject"])("reset ignores late %s completion", async phase => {
  const state = setup();
  let finish!: (response: Response) => void, reject!: (error: Error) => void;
  if (phase === "content") state.fetcher.mockResolvedValueOnce(saved());
  state.fetcher.mockImplementationOnce(() => new Promise((resolve, fail) => { finish = resolve; reject = fail; }));
  let running!: Promise<void>;
  await act(async () => { running = state.result.current.restore(selected); });
  act(() => state.result.current.reset());
  await act(async () => { if (phase === "reject") reject(new Error("offline")); else finish(phase === "content" ? content() : saved()); await running; });
  expect(state.onRestored).not.toHaveBeenCalled(); expect(state.result.current.pending).toBeNull();
  state.unmount();
});
