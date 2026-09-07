import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DownloadVersion } from "../src/workspace/DownloadVersion";
import { HistoricalPreview } from "../src/workspace/HistoricalPreview";
import { setLanguage } from "../src/i18n";

beforeEach(async () => { await setLanguage("en"); });

test("historical download rejects errors and mismatched identity, then cleans up exact successful download", async () => {
  const create = vi.fn(() => "blob:revision"), revoke = vi.fn();
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }));
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { expect(this.download).toBe("Їжак.docx"); });
  const fetcher = vi.fn<(request: Request) => Promise<Response>>()
    .mockResolvedValueOnce(Response.json({ error: { code: "not_found" } }, { status: 404 }))
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(new Response("wrong", { headers: { "X-Fillable-Version": "other" } }))
    .mockResolvedValueOnce(new Response("exact", { headers: { "X-Fillable-Version": "selected" } }));
  vi.stubGlobal("fetch", fetcher);
  render(<DownloadVersion identity="document" version="selected" filename="Їжак.docx" />);
  fireEvent.click(screen.getByRole("button")); await screen.findByText("Not found.");
  fireEvent.click(screen.getByRole("button")); await screen.findByText(/Something went wrong/);
  fireEvent.click(screen.getByRole("button")); await screen.findByText(/different revision/);
  expect(create).not.toHaveBeenCalled();
  await act(() => setLanguage("uk"));
  expect(screen.getByText(/Сервер повернув іншу версію/)).toBeVisible();
  fireEvent.click(screen.getByRole("button"));
  await waitFor(() => expect(click).toHaveBeenCalledTimes(1));
  expect(create).toHaveBeenCalledTimes(1); expect(document.querySelector('a[download]')).toBeNull();
  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:revision"), { timeout: 2000 });
});

test.each(["resolve", "reject"])("unmount aborts a historical download and ignores late %s", async phase => {
  let finish!: (value: Response) => void, fail!: (error: Error) => void;
  const fetcher = vi.fn<(request: Request) => Promise<Response>>().mockImplementation(() => new Promise((resolve, reject) => { finish = resolve; fail = reject; }));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<DownloadVersion identity="document" version="selected" filename="Їжак.docx" />);
  fireEvent.click(screen.getByRole("button")); fireEvent.click(screen.getByRole("button"));
  expect(fetcher).toHaveBeenCalledTimes(1); view.unmount();
  expect(fetcher.mock.calls[0][0].signal.aborted).toBe(true);
  await act(async () => { if (phase === "resolve") finish(new Response("late")); else fail(new Error("late")); });
});

test("plain historical preview is read-only with no fabricated fields", async () => {
  const document = { type: "doc", content: [{ type: "section", attrs: { part: "word/document.xml" }, content: [{ type: "paragraph", attrs: { id: "paragraph" }, content: [{ type: "text", text: "Збережений текст" }] }] }] };
  render(<HistoricalPreview document={document} />);
  const editor = screen.getByRole("textbox", { name: "Read-only historical document" });
  expect(editor).toHaveAttribute("contenteditable", "false");
  expect(editor).toHaveTextContent("Збережений текст");
  fireEvent.click(screen.getByText("Saved fields"));
  expect(screen.getByText("No fields in this saved revision.")).toBeVisible();
});
