import { StrictMode } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { useEditingLease } from "../src/workspace/useEditingLease";
import type { Resource } from "../src/library/useLibrary";
import { leaseResponse } from "./lease-response";

const resource = { id: "11111111-1111-4111-8111-111111111111", current_version_id: "22222222-2222-4222-8222-222222222222" } as Resource;
const failed = (reason: string) => Response.json({ error: { code: "operation_conflict", parameters: { reason } } }, { status: 409 });
function Host({ item = resource }: { item?: Resource | null }) {
  const access = useEditingLease(item, "csrf");
  return <><p role="status">{access.status}:{access.error}</p><button onClick={access.retry}>Retry</button>
    <button onClick={event => { event.currentTarget.textContent = access.canEdit() ? "allowed" : "blocked"; }}>Check</button></>;
}
const advance = async (time = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(time); }); };
beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

test("StrictMode acquires on HTTP without randomUUID, renews and releases one generation", async () => {
  vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
  const fetcher = vi.fn(leaseResponse); vi.stubGlobal("fetch", fetcher);
  const view = render(<StrictMode><Host /></StrictMode>);
  await advance(); expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status")).toHaveTextContent("active:");
  const initial = fetcher.mock.calls[0][0]; expect(initial.headers.get("X-CSRF-Token")).toBe("csrf");
  const body = await initial.clone().json();
  await advance(20000);
  const renewed = await fetcher.mock.calls[1][0].clone().json();
  expect(renewed).toMatchObject({ action: "renew", client_id: body.client_id, lease_id: "33333333-3333-4333-8333-333333333333" });
  view.unmount(); await advance();
  expect(await fetcher.mock.calls.at(-1)![0].clone().json()).toMatchObject({ action: "release", client_id: body.client_id, lease_id: renewed.lease_id });
});

test("conflict is paused until explicit retry and synchronous deadline rejects suspended-timer edits", async () => {
  let clock = 0; vi.spyOn(performance, "now").mockImplementation(() => clock);
  const fetcher = vi.fn().mockResolvedValueOnce(failed("lease_busy")).mockImplementation(leaseResponse);
  vi.stubGlobal("fetch", fetcher); render(<Host />); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("paused:lease_busy");
  fireEvent.click(screen.getByText("Retry")); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("active:");
  clock = 61000;
  fireEvent.click(screen.getByText("Check")); expect(screen.getByText("blocked")).toBeVisible();
  fireEvent(window, new Event("focus")); expect(screen.getByRole("status")).toHaveTextContent("paused:lease_lost");
  fireEvent.click(screen.getByText("Retry")); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("active:");
  fireEvent(window, new Event("pagehide")); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("paused:lease_lost");
});

test("late renewal cannot silently resume an expired draft and timeout/network errors pause", async () => {
  let clock = 0; vi.spyOn(performance, "now").mockImplementation(() => clock);
  let finish!: (response: Response) => void;
  const fetcher = vi.fn().mockImplementationOnce(leaseResponse).mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
  vi.stubGlobal("fetch", fetcher); render(<Host />); await advance();
  clock = 20000; await advance(20000);
  fireEvent.click(screen.getByText("Retry")); expect(fetcher).toHaveBeenCalledTimes(2);
  clock = 61000;
  await act(async () => finish(await leaseResponse(fetcher.mock.calls[1][0])));
  expect(screen.getByRole("status")).toHaveTextContent("paused:lease_lost");
  fetcher.mockRejectedValueOnce(new Error("offline"));
  fireEvent.click(screen.getByText("Retry")); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("paused:internal_error");
  fetcher.mockImplementationOnce((request: Request) => new Promise((_resolve, reject) => { request.signal.addEventListener("abort", () => reject(new Error("timeout"))); }));
  fireEvent.click(screen.getByText("Retry")); await advance(10000);
  expect(screen.getByRole("status")).toHaveTextContent("paused:internal_error");
});

test("malformed/stale responses never enable editing; unmount cancels pending acquisition", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(failed("revision"))
    .mockResolvedValueOnce(Response.json({ status: "active", source_version_id: "other", lease_id: "generation", valid_for_seconds: 60 }))
    .mockResolvedValueOnce(Response.json({ error: { code: "authentication_required" } }, { status: 401 }));
  vi.stubGlobal("fetch", fetcher); const view = render(<Host />); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("paused:revision");
  fireEvent.click(screen.getByText("Retry")); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("paused:lease_lost");
  fireEvent.click(screen.getByText("Retry")); await advance();
  expect(screen.getByRole("status")).toHaveTextContent("paused:authentication_required");
  let finish!: (response: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByText("Retry")); await advance();
  const request = fetcher.mock.calls.at(-1)![0] as Request;
  view.unmount(); expect(request.signal.aborted).toBe(true);
  await act(async () => finish(await leaseResponse(request)));
  expect(screen.queryByRole("status")).toBeNull();
  render(<Host item={null} />); fireEvent.click(screen.getByText("Retry")); await advance();
  expect(fetcher).toHaveBeenCalledTimes(4);
});
