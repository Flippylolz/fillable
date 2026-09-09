import { leaseResponse } from "./lease-response";
import { StrictMode, useCallback, useState } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Workspace } from "../src/workspace/Workspace";
import { WorkspaceSettings } from "../src/workspace/WorkspaceSettings";
import type { Resource } from "../src/library/useLibrary";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

const resource = { id: "11111111-1111-4111-8111-111111111111", kind: "template", title: "Заява Ґанни", original_filename: "Заява.docx", current_version_id: "22222222-2222-4222-8222-222222222222", created_at: "2026-09-06", updated_at: "2026-09-06", size_bytes: 3, digest: "hash", unsupported_count: 1, deletion_pending: false, processing_status: "not_started" };
const failure = (code: string, reason?: string) => Response.json({ error: { code, parameters: { reason } } }, { status: 409 });
function setup(patch?: (request: Request) => Promise<Response>) {
  const server = { current: { ...resource } };
  const changed = vi.fn(), back = vi.fn(), busy = vi.fn();
  const writes = vi.fn(patch ?? (async (request: Request) => {
    const body = await request.clone().json(); server.current = { ...server.current, title: body.title };
    return Response.json(server.current);
  }));
  const fetcher = vi.fn(async (request: Request) => {
    if (request.method === "PATCH") return writes(request);
    const path = new URL(request.url).pathname;
    if (path.endsWith("/editing-lease")) return leaseResponse(request);
    if (path.endsWith("/content")) return Response.json({ resource: server.current, document: corpus });
    if (path.endsWith("/fields")) return Response.json({ source_version_id: server.current.current_version_id, status: "not_started", snapshot: null });
    return Response.json(server.current);
  });
  vi.stubGlobal("fetch", fetcher);
  function Harness() {
    const [dirty, setDirty] = useState(false);
    const mark = useCallback((value: boolean) => setDirty(value), []);
    return <Workspace identity={resource.id} csrfToken="csrf" dirty={dirty} onDirty={mark} onChanged={changed} onBusy={busy} onBack={back} />;
  }
  const view = render(<StrictMode><I18nextProvider i18n={i18n}><Harness /></I18nextProvider></StrictMode>);
  return { ...view, server, writes, changed, back, busy, fetcher };
}
async function open() {
  await screen.findByText("Editing enabled.");
  await screen.findByRole("textbox", { name: "Editable document" });
  fireEvent.click(await screen.findByText("Workspace settings"));
}
beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("view settings and locale retain the same editor while rename preserves a document draft", async () => {
  const { writes, changed, back, container } = setup(); await open();
  const editor = screen.getByRole("textbox", { name: "Editable document" });
  const original = editor.textContent;
  fireEvent.change(screen.getByRole("combobox", { name: "Zoom" }), { target: { value: "1.25" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "Highlight fields" }));
  expect(container.querySelector(".document-workbench")).toHaveStyle({ "--document-zoom": "1.25" });
  expect(container.querySelector(".document-workbench")).toHaveAttribute("data-highlight-fields", "false");
  expect(screen.getByText("Saved revision opened.")).toBeVisible();
  expect(editor.textContent).toBe(original); expect(writes).not.toHaveBeenCalled();
  const field = screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0];
  fireEvent.change(field, { target: { value: "Чернетка Їжака" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Title" }), { target: { value: "Нова назва" } });
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("textbox", { name: "Назва" })).toHaveValue("Нова назва");
  expect(screen.getByRole("combobox", { name: "Масштаб" })).toHaveValue("1.25");
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  fireEvent.click(screen.getByRole("button", { name: "Перейменувати" }));
  await screen.findByText("Назву збережено.");
  expect(screen.getByRole("heading", { name: "Нова назва" })).toBeVisible();
  expect(editor).toHaveTextContent("Чернетка Їжака");
  expect(screen.getByText(/Є незбережені зміни/)).toBeVisible();
  expect(changed).toHaveBeenCalledTimes(1);
  expect(writes.mock.calls[0][0].headers.get("X-CSRF-Token")).toBe("csrf");
  fireEvent.click(screen.getByRole("button", { name: "Назад до бібліотеки" }));
  expect(back).toHaveBeenCalledTimes(1);
});

test("invalid and pending renames retain input and successful metadata-only rename clears dirty state", async () => {
  let finish!: (response: Response) => void;
  const { writes } = setup(() => new Promise(resolve => { finish = resolve; })); await open();
  const input = screen.getByRole("textbox", { name: "Title" });
  for (const value of [" ", "🙂".repeat(161), "bad\u0000title", "\ud800"]) {
    fireEvent.change(input, { target: { value } });
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription(/160/);
    expect(input).toHaveValue(value);
  }
  expect(writes).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: "Оновлена назва" } });
  fireEvent.submit(input.closest("form")!); fireEvent.submit(input.closest("form")!);
  expect(writes).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Back to library" })).toBeDisabled();
  await act(async () => finish(Response.json({ ...resource, title: "Оновлена назва" })));
  await screen.findByText("Title saved.");
  expect(screen.getByText("Saved revision opened.")).toBeVisible();
});

test("title conflicts reload current metadata without discarding the proposed name", async () => {
  const { server, writes } = setup(); await open();
  const input = screen.getByRole("textbox", { name: "Title" });
  fireEvent.change(input, { target: { value: "Мій варіант" } });
  server.current.title = "Інший варіант";
  writes.mockResolvedValueOnce(failure("operation_conflict", "title"));
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByText(/The title changed elsewhere/);
  fireEvent.click(screen.getByRole("button", { name: "Reload current title" }));
  await screen.findByText(/Current title reloaded/);
  expect(input).toHaveValue("Мій варіант");
  expect(screen.getByRole("heading", { name: "Інший варіант" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByText("Title saved.");
  expect(await writes.mock.calls[1][0].clone().json()).toMatchObject({ previous_title: "Інший варіант", title: "Мій варіант" });
});

test("a new saved revision requires explicit discard before reopening and retains the title on cancellation", async () => {
  const { server, writes } = setup(); await open();
  fireEvent.change(screen.getByRole("textbox", { name: "Title" }), { target: { value: "Чернетка назви" } });
  writes.mockResolvedValueOnce(failure("operation_conflict", "title"));
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByRole("button", { name: "Reload current title" });
  server.current.current_version_id = "33333333-3333-4333-8333-333333333333";
  fireEvent.click(screen.getByRole("button", { name: "Reload current title" }));
  await screen.findByText(/The saved revision changed/);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.click(screen.getByRole("button", { name: "Reopen saved document" }));
  expect(confirm).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Чернетка назви");
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole("button", { name: "Reopen saved document" }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Title", hidden: true })).toHaveValue(resource.title));
});

test("workspace-held open state keeps the settings panel expanded across remounts", () => {
  const onOpenChange = vi.fn();
  const item = resource as Resource;
  function view(open: boolean, key = 1) {
    return <I18nextProvider i18n={i18n}><WorkspaceSettings key={key} open={open} onOpenChange={onOpenChange}
      item={item} csrfToken="csrf" zoom={1} highlight onZoom={vi.fn()} onHighlight={vi.fn()}
      onResource={vi.fn()} onDirty={vi.fn()} onReopen={vi.fn()} /></I18nextProvider>;
  }
  const mounted = render(view(false));
  const details = () => mounted.container.querySelector(".workspace-settings") as HTMLDetailsElement;
  expect(details().open).toBe(false);
  fireEvent.click(screen.getByText("Workspace settings"));
  // jsdom flips the attribute without dispatching toggle; real browsers dispatch it from the click.
  act(() => { details().open = true; details().dispatchEvent(new Event("toggle")); });
  expect(onOpenChange).toHaveBeenCalledWith(true);
  mounted.rerender(view(true));
  expect(details().open).toBe(true);
  expect(screen.getByRole("textbox", { name: "Title" })).toBeVisible();
  // The editor epoch remounts the panel after restore/reopen; the workspace keeps it expanded.
  mounted.rerender(view(true, 2));
  expect(details().open).toBe(true);
  expect(screen.getByRole("textbox", { name: "Title" })).toBeVisible();
  mounted.rerender(view(false));
  expect(details().open).toBe(false);
  mounted.unmount();
});

test("network/session failures retain drafts and unmount aborts a late rename", async () => {
  let finish!: (response: Response) => void;
  const { writes, changed, unmount } = setup(); await open();
  const input = screen.getByRole("textbox", { name: "Title" });
  fireEvent.change(input, { target: { value: "Надійна чернетка" } });
  writes.mockRejectedValueOnce(new Error("offline"));
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByRole("alert"); expect(input).toHaveValue("Надійна чернетка");
  writes.mockResolvedValueOnce(failure("authentication_required"));
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByRole("alert"); expect(input).toHaveValue("Надійна чернетка");
  writes.mockResolvedValueOnce(failure("operation_conflict", "revision"));
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByText(/The saved revision changed/);
  writes.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  const request = writes.mock.calls.at(-1)![0]; unmount();
  expect(request.signal.aborted).toBe(true);
  await act(async () => finish(Response.json({ ...resource, title: "Надійна чернетка" })));
  expect(changed).not.toHaveBeenCalled();
});
