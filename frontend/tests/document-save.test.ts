import { act, renderHook } from "@testing-library/react";
import { useDocumentSave } from "../src/workspace/useDocumentSave";
import type { EditorSnapshot } from "../src/editor/adapter";
import type { EditingCredentials } from "../src/workspace/useEditingLease";

const credentials: EditingCredentials = { source_version_id: "22222222-2222-4222-8222-222222222222", client_id: "33333333-3333-4333-8333-333333333333", lease_id: "44444444-4444-4444-8444-444444444444" };
const saved = () => Response.json({ saved_version_id: "new", resource: { current_version_id: "new" } });
function setup() {
  const snapshot: EditorSnapshot = { document: { type: "doc", attrs: { review: { sourceVersion: null, items: [] } } }, revision: 1, fieldValuesValid: true, composing: false };
  const read = vi.fn<() => EditorSnapshot | null>(() => structuredClone(snapshot));
  const lease = vi.fn<() => EditingCredentials | undefined>(() => credentials);
  const onSaved = vi.fn(), onAccessLost = vi.fn();
  const fetcher = vi.fn<(request: Request) => Promise<Response>>().mockResolvedValue(saved());
  vi.stubGlobal("fetch", fetcher);
  const view = renderHook(() => useDocumentSave({ identity: "11111111-1111-4111-8111-111111111111", csrfToken: "csrf", read, credentials: lease, onSaved, onAccessLost }));
  return { ...view, snapshot, read, lease, fetcher, onSaved, onAccessLost };
}

test("save checks the synchronous snapshot for composition, validity, availability and already acknowledged revisions", async () => {
  const state = setup();
  state.read.mockReturnValueOnce(null);
  await act(() => state.result.current.save()); expect(state.result.current.error).toBe("lease_lost");
  state.lease.mockReturnValueOnce(undefined);
  await act(() => state.result.current.save()); expect(state.fetcher).not.toHaveBeenCalled();
  state.snapshot.composing = true;
  await act(() => state.result.current.save()); expect(state.result.current.error).toBe("composing");
  state.snapshot.composing = false; state.snapshot.fieldValuesValid = false;
  await act(() => state.result.current.save()); expect(state.result.current.error).toBe("invalid_fields");
  state.snapshot.fieldValuesValid = true; state.snapshot.revision = 0;
  await act(() => state.result.current.save()); expect(state.fetcher).not.toHaveBeenCalled();
  state.snapshot.revision = 1;
  await act(() => state.result.current.save());
  expect(state.result.current.acknowledged).toBe(1); expect(state.result.current.reviewSaved).toBe(true);
  await act(() => state.result.current.save()); expect(state.fetcher).toHaveBeenCalledTimes(1);
});

test("timeout keeps one immutable attempt, rejects concurrent requests and retries without reading newer invalid input", async () => {
  vi.useFakeTimers();
  try {
    const state = setup();
    state.fetcher.mockImplementationOnce(request => new Promise((_resolve, reject) => {
      request.signal.addEventListener("abort", () => reject(new Error("timed out")));
    }));
    let running!: Promise<void>;
    await act(async () => { running = state.result.current.save(); });
    await act(() => state.result.current.save()); expect(state.fetcher).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(45000); await running; });
    expect(state.result.current).toMatchObject({ busy: false, pending: true, error: "internal_error" });
    state.read.mockReturnValue(null); state.lease.mockReturnValue(undefined);
    await act(() => state.result.current.save());
    expect(state.result.current).toMatchObject({ pending: false, acknowledged: 1 });
    expect(await state.fetcher.mock.calls[1][0].clone().json()).toEqual(await state.fetcher.mock.calls[0][0].clone().json());
    expect(state.fetcher.mock.calls[1][0].headers.get("Idempotency-Key")).toBe(state.fetcher.mock.calls[0][0].headers.get("Idempotency-Key"));
  } finally { vi.useRealTimers(); }
});

test.each(["operation_in_progress", "dependencies_unavailable"])("%s preserves the attempt until a committed result", async code => {
  const state = setup();
  state.fetcher.mockResolvedValueOnce(Response.json({ error: { code } }, { status: code === "operation_in_progress" ? 409 : 503 }));
  await act(() => state.result.current.save()); expect(state.result.current.pending).toBe(true);
  await act(() => state.result.current.save()); expect(state.onSaved).toHaveBeenCalledTimes(1);
});

test.each(["lease_lost", "revision", "authentication_required", "forbidden"])("%s pauses access and retains the unsaved draft", async error => {
  const state = setup();
  const conflict = ["lease_lost", "revision"].includes(error);
  state.fetcher.mockResolvedValueOnce(Response.json({ error: { code: conflict ? "operation_conflict" : error, parameters: { reason: error } } }, { status: 409 }));
  await act(() => state.result.current.save());
  expect(state.onAccessLost).toHaveBeenCalledWith(error); expect(state.onSaved).not.toHaveBeenCalled();
  expect(state.result.current).toMatchObject({ pending: false, acknowledged: 0, error });
  if (error === "revision") { await act(() => state.result.current.save()); expect(state.fetcher).toHaveBeenCalledTimes(1); }
});

test("unknown conflict blocks fresh saves until explicit reopen reset", async () => {
  const state = setup(); state.fetcher.mockResolvedValueOnce(Response.json({ error: { code: "operation_conflict" } }, { status: 409 }));
  await act(() => state.result.current.save()); expect(state.result.current.conflict).toBe(true);
  act(() => state.result.current.reset());
  await act(() => state.result.current.save()); expect(state.onSaved).toHaveBeenCalledTimes(1);
});

test.each(["reset", "unmount"] as const)("%s aborts a pending request and ignores a late result", async action => {
  const state = setup(); let finish!: (response: Response) => void;
  state.fetcher.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  let running!: Promise<void>;
  await act(async () => { running = state.result.current.save(); });
  const request = state.fetcher.mock.calls[0][0];
  act(() => { if (action === "reset") state.result.current.reset(); else state.unmount(); });
  expect(request.signal.aborted).toBe(true);
  await act(async () => { finish(saved()); await running; });
  expect(state.onSaved).not.toHaveBeenCalled();
});
