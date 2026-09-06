import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { DeleteResource } from "../src/library/DeleteResource";
import type { Resource } from "../src/library/useLibrary";
import { i18n, setLanguage } from "../src/i18n";
const item: Resource = { id: "id", kind: "document", title: "Заява Їжака", original_filename: "Заява.docx", current_version_id: "v1", created_at: "2026-09-06", updated_at: "2026-09-06", size_bytes: 3, digest: "hash", unsupported_count: 0, deletion_pending: false, processing_status: "not_started" };
const changed = vi.fn(); const busy = vi.fn();
function show(pending = false) { return render(<I18nextProvider i18n={i18n}><DeleteResource item={{ ...item, deletion_pending: pending }} csrfToken="csrf" disabled={false} onBusy={busy} onChanged={changed} /></I18nextProvider>); }
beforeEach(async () => {
  await setLanguage("uk"); changed.mockClear(); busy.mockClear();
  // jsdom has no dialog methods; real modal/focus behavior is checked in Playwright.
  HTMLDialogElement.prototype.showModal = function() { this.open = true; };
  HTMLDialogElement.prototype.close = function() { this.open = false; };
});
afterEach(() => {
  delete (HTMLDialogElement.prototype as Partial<HTMLDialogElement>).showModal;
  delete (HTMLDialogElement.prototype as Partial<HTMLDialogElement>).close;
});

test("cancel never deletes; confirmed failure remains retryable in the selected language", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ error: { code: "operation_conflict" } }, { status: 409 }))
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(Response.json({ status: "complete" }));
  vi.stubGlobal("fetch", fetcher); show();
  fireEvent.click(screen.getByRole("button", { name: "Видалити" }));
  expect(screen.getByRole("dialog")).toHaveAccessibleName("Видалити «Заява Їжака»?");
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));
  expect(fetcher).not.toHaveBeenCalled();
  for (let attempt = 0; attempt < 2; attempt++) {
    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));
    fireEvent.click(screen.getByRole("button", { name: "Видалити назавжди" }));
    await screen.findByRole("alert"); expect(changed).not.toHaveBeenCalled();
  }
  await act(() => setLanguage("en"));
  fireEvent.click(screen.getByRole("button", { name: "Delete" }));
  expect(screen.getByRole("dialog")).toHaveAccessibleDescription(/original and all saved versions/);
  fireEvent.click(screen.getByRole("button", { name: "Delete permanently" }));
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  expect(fetcher.mock.calls[2][0].headers.get("x-csrf-token")).toBe("csrf");
  expect(busy).toHaveBeenLastCalledWith(false);
});

test("already-confirmed pending cleanup can resume without a second confirmation and refreshes usage", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ status: "pending" })));
  show(true); fireEvent.click(screen.getByRole("button", { name: "Повторити очищення" }));
  await waitFor(() => expect(changed).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("unmount aborts a pending deletion and ignores its late result", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(resolve => { finish = resolve; })));
  const view = show(true);
  fireEvent.click(screen.getByRole("button")); fireEvent.click(screen.getByRole("button"));
  expect(fetch).toHaveBeenCalledTimes(1);
  view.unmount(); await act(async () => finish(Response.json({ status: "complete" })));
  expect(changed).not.toHaveBeenCalled(); expect(busy).toHaveBeenLastCalledWith(false);
});
