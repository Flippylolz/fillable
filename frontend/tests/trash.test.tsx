import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { TrashActions } from "../src/library/TrashActions";
import { Library } from "../src/library/Library";
import { App } from "../src/App";
import { setLanguage } from "../src/i18n";
import type { Resource } from "../src/library/useLibrary";

const item: Resource = { id: "trash-id", kind: "template", title: "Ґанна", original_filename: "test.docx", current_version_id: "version", created_at: "2026-09-01", updated_at: "2026-09-01", size_bytes: 100, digest: "a", unsupported_count: 0, deletion_pending: false, preview_ready: false, processing_status: "not_started", purge_after: "2026-10-16T12:00:00Z" };
const busy = vi.fn(), changed = vi.fn();
const props = { csrfToken: "csrf", disabled: false, onBusy: busy, onChanged: changed };
beforeEach(async () => { await setLanguage("en"); busy.mockClear(); changed.mockClear(); vi.spyOn(window, "confirm").mockReturnValue(true); });
const success = () => Response.json({ status: "complete" });

test("restore is immediate, permanent deletion requires confirmation, and empty trash reports pending cleanup", async () => {
  const fetcher = vi.fn().mockImplementation(success); vi.stubGlobal("fetch", fetcher);
  const view = render(<TrashActions {...props} item={item} />);
  fireEvent.click(screen.getByText("Restore"));
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  expect(fetcher.mock.calls[0][0].url).toMatch(/trash-id\/untrash$/);
  expect(fetcher.mock.calls[0][0].headers.get("x-csrf-token")).toBe("csrf");
  expect(window.confirm).not.toHaveBeenCalled();
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  fireEvent.click(screen.getByText("Delete permanently"));
  expect(fetcher).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByText("Delete permanently"));
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(2));
  expect(fetcher.mock.calls[1][0].method).toBe("DELETE");
  view.rerender(<TrashActions {...props} />);
  fetcher.mockResolvedValueOnce(Response.json({ status: "pending" }));
  fireEvent.click(screen.getByText("Empty trash"));
  await screen.findByRole("status");
  expect(fetcher.mock.calls[2][0].url).toMatch(/documents\/trash$/);
});

test("failures retain recoverable actions and busy or disabled controls prevent duplicate calls", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ error: { code: "operation_conflict" } }, { status: 409 })).mockRejectedValueOnce(new Error("offline"));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<TrashActions {...props} item={item} />);
  fireEvent.click(screen.getByText("Restore")); await screen.findByRole("alert");
  expect(changed).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText("Restore")); await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByText("Restore")).toBeEnabled());
  let finish!: (response: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByText("Restore")); fireEvent.click(screen.getByText("Restore"));
  expect(fetcher).toHaveBeenCalledTimes(3);
  view.unmount(); await act(async () => finish(success()));
  expect(changed).not.toHaveBeenCalled();
  expect(busy).toHaveBeenLastCalledWith(false);
  render(<TrashActions {...props} item={item} disabled />);
  fireEvent.click(screen.getByText("Restore")); expect(fetcher).toHaveBeenCalledTimes(3);
});

test("an aborted network rejection never updates an unmounted trash action", async () => {
  let reject!: (error: Error) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((_, no) => { reject = no; })));
  const view = render(<TrashActions {...props} />);
  fireEvent.click(screen.getByText("Empty trash")); view.unmount();
  await act(async () => reject(new Error("aborted")));
  expect(changed).not.toHaveBeenCalled();
});

test("trash gallery shows deadlines, hides document actions, and refreshes after restore and empty", async () => {
  let items = [item, { ...item, id: "pending", title: "Pending", deletion_pending: true, purge_after: null }];
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (request.method !== "GET") { items = []; return success(); }
    expect(new URL(request.url).searchParams.get("kind")).toBe("trash");
    return Response.json({ items, next_cursor: null });
  }));
  const view = render(<Library csrfToken="csrf" disabled={false} onBusy={busy} onDirty={vi.fn()} onSaved={changed} tab="trash" />);
  const card = await screen.findByRole("article", { name: "Ґанна" });
  expect(within(card).getByText(/Recoverable until/)).toBeVisible();
  expect(within(card).queryByRole("link")).toBeNull();
  expect(within(screen.getByRole("article", { name: "Pending" })).queryByText("Restore")).toBeNull();
  fireEvent.click(within(card).getByText("Restore"));
  await screen.findByText("Trash is empty.");
  expect(changed).toHaveBeenCalled();
  view.unmount(); items = [item];
  render(<Library csrfToken="csrf" disabled={false} onBusy={busy} onDirty={vi.fn()} onSaved={changed} tab="trash" />);
  await screen.findByRole("article", { name: "Ґанна" });
  fireEvent.click(screen.getByText("Empty trash")); await screen.findByText("Trash is empty.");
});

test("sidebar opens the localized trash section", async () => {
  window.history.replaceState(null, "", "/documents");
  const session = { csrf_token: "csrf", user: { id: "owner", login: "owner", display_name: "Owner", role: "user", ui_language: "en" } };
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/auth/session") return Response.json(session);
    if (path === "/api/health") return Response.json({ status: "ok" });
    if (path === "/api/storage/usage") return Response.json({ used_bytes: 0, reserved_bytes: 0, limit_bytes: 100, available_bytes: 100, over_limit: false });
    return Response.json({ items: [], next_cursor: null });
  }));
  render(<App />);
  fireEvent.click(await screen.findByRole("link", { name: "Trash" }));
  expect(await screen.findByRole("heading", { name: "Trash" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Trash" })).toHaveAttribute("aria-current", "page");
});
