import { act, fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { ProcessingStatus } from "../src/library/ProcessingStatus";
import type { Resource } from "../src/library/useLibrary";
import { i18n, setLanguage } from "../src/i18n";

const item = { id: "doc", current_version_id: "v1", processing_status: "queued" } as Resource;
const response = (status: string, version = "v1") => Response.json({ status, source_version_id: version });
function ui(disabled = false) { return <I18nextProvider i18n={i18n}><ProcessingStatus item={item} csrfToken="csrf" disabled={disabled} /></I18nextProvider>; }
async function flush() { await act(async () => { await new Promise(resolve => setImmediate(resolve)); }); }
beforeEach(async () => { await setLanguage("uk"); vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }); });
afterEach(() => vi.useRealTimers());

test("polling follows the current saved revision, survives language changes and stops on success", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response("queued")).mockResolvedValueOnce(response("running")).mockResolvedValueOnce(response("succeeded"));
  vi.stubGlobal("fetch", fetcher); const view = render(ui()); await flush();
  expect(screen.getByRole("status")).toHaveTextContent("Перевірка в черзі");
  view.rerender(ui(true));
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(screen.getByRole("status")).toHaveTextContent("Перевіряємо документ");
  await act(() => setLanguage("en"));
  expect(screen.getByRole("status")).toHaveTextContent("Inspecting document");
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(screen.getByRole("status")).toHaveTextContent("Inspection complete");
  await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
  expect(fetcher).toHaveBeenCalledTimes(3);
});

test("network and API failures preserve known status; retrying inspection uses CSRF and no duplicate pending request", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(Response.json({ error: { code: "not_found" } }, { status: 404 }))
    .mockResolvedValueOnce(response("failed"));
  vi.stubGlobal("fetch", fetcher); const view = render(ui()); await flush();
  expect(screen.getByRole("status")).toHaveTextContent("Перевірка в черзі");
  for (let i = 0; i < 2; i++) { fireEvent.click(screen.getByRole("button")); await flush(); }
  expect(screen.getByRole("status")).toHaveTextContent("Не вдалося перевірити");
  view.rerender(ui(true)); expect(screen.getByRole("button")).toBeDisabled();
  view.rerender(ui());
  let finish!: (value: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByRole("button")); fireEvent.click(screen.getByRole("button")); await flush();
  expect(fetcher).toHaveBeenCalledTimes(4);
  const request = fetcher.mock.calls[3][0] as Request;
  expect(request.method).toBe("POST"); expect(request.headers.get("X-CSRF-Token")).toBe("csrf");
  await act(async () => finish(response("queued"))); await flush();
  expect(screen.queryByRole("alert")).toBeNull();
  view.unmount(); await vi.advanceTimersByTimeAsync(5000); expect(fetcher).toHaveBeenCalledTimes(4);
});

test.each([false, true])("unmount aborts and ignores late response or rejection (%s)", async failure => {
  let finish!: (value: Response) => void; let reject!: (value: Error) => void;
  const fetcher = vi.fn((_request: Request) => new Promise<Response>((resolve, fail) => { finish = resolve; reject = fail; }));
  vi.stubGlobal("fetch", fetcher); const view = render(ui()); await flush(); view.unmount();
  expect((fetcher.mock.calls[0][0] as Request).signal.aborted).toBe(true);
  await act(async () => { if (failure) reject(new Error("late")); else finish(response("queued")); });
  await vi.advanceTimersByTimeAsync(5000); expect(fetcher).toHaveBeenCalledTimes(1);
});

test("legacy revision can be submitted and a newer revision result never replaces its status", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response("not_started")).mockResolvedValueOnce(response("succeeded", "v2"));
  vi.stubGlobal("fetch", fetcher); render(ui()); await flush();
  expect(screen.getByRole("button")).toHaveTextContent("Перевірити документ");
  fireEvent.click(screen.getByRole("button")); await flush();
  expect(screen.getByRole("status")).toHaveTextContent("попередньої версії");
  await vi.advanceTimersByTimeAsync(5000); expect(fetcher).toHaveBeenCalledTimes(2);
});
