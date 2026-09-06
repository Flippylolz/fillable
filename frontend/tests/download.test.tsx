import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { DownloadSaved } from "../src/library/DownloadSaved";
import type { Resource } from "../src/library/useLibrary";
import { i18n, setLanguage } from "../src/i18n";

const item: Resource = { id: "id", kind: "document", title: "Заява", original_filename: "Заява-Їжак.docx", current_version_id: "v1", created_at: "2026-09-06", updated_at: "2026-09-06", size_bytes: 3, digest: "hash", unsupported_count: 0, processing_status: "not_started" };
function show(disabled = false) { return render(<I18nextProvider i18n={i18n}><DownloadSaved item={item} disabled={disabled} /></I18nextProvider>); }
beforeEach(async () => {
  await setLanguage("uk");
  URL.createObjectURL = vi.fn(() => "blob:download");
  URL.revokeObjectURL = vi.fn();
});

test("failed download preserves retry and never creates an empty file; success keeps the filename and frees the URL", async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(Response.json({ error: { code: "not_found" } }, { status: 404 }))
    .mockResolvedValueOnce(new Response("DOCX bytes"));
  vi.stubGlobal("fetch", fetcher);
  const clicked = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function(this: HTMLAnchorElement) {
    expect(this.download).toBe(item.original_filename);
    expect(this.href).toBe("blob:download");
    expect(this.isConnected).toBe(true);
  });
  show();
  for (let attempt = 0; attempt < 2; attempt++) {
    fireEvent.click(screen.getByRole("button"));
    await screen.findByRole("alert");
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(clicked).not.toHaveBeenCalled();
  }
  await act(() => setLanguage("en"));
  expect(screen.getByRole("button")).toHaveTextContent("Download saved DOCX");
  fireEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(clicked).toHaveBeenCalledTimes(1));
  const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0] as Blob;
  expect(await blob.text()).toBe("DOCX bytes");
  expect(fetcher.mock.calls[2][0].url).toMatch(/\/api\/documents\/id\/download$/);
  expect(document.querySelector('a[download]')).toBeNull();
  await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:download"), { timeout: 1500 });
  expect(screen.queryByRole("alert")).toBeNull();
});

test("pending and disabled controls cannot duplicate downloads; unmount aborts and ignores late bytes", async () => {
  let finish!: (response: Response) => void;
  const fetcher = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  const view = show(true);
  fireEvent.click(screen.getByRole("button")); expect(fetcher).not.toHaveBeenCalled();
  view.rerender(<I18nextProvider i18n={i18n}><DownloadSaved item={item} disabled={false} /></I18nextProvider>);
  fireEvent.click(screen.getByRole("button"));
  fireEvent.click(screen.getByRole("button"));
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button")).toBeDisabled();
  view.unmount();
  await act(async () => finish(new Response("late bytes")));
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});
