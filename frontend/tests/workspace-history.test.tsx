import { StrictMode, useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import { leaseResponse } from "./lease-response";

const id = "11111111-1111-4111-8111-111111111111", v1 = "22222222-2222-4222-8222-222222222222", v2 = "33333333-3333-4333-8333-333333333333", v3 = "44444444-4444-4444-8444-444444444444";
const version = (identity: string, number: number) => ({ id: identity, number, created_at: "2026-09-07T09:00:00Z", size_bytes: 1536000,
  digest: "digest", unsupported_count: 1, is_current: identity === v2, parent_version_id: number > 1 ? v1 : null, restored_from_version_id: null as string | null, restored_from_number: null as number | null });
const resource = { id, kind: "document", title: "Заява Їжака", original_filename: "Їжак.docx", current_version_id: v2,
  created_at: "2026-09-07", updated_at: "2026-09-07", size_bytes: 1536000, digest: "digest", unsupported_count: 1, deletion_pending: false, processing_status: "not_started" };
const failure = (code = "internal_error", status = 503) => Response.json({ error: { code } }, { status });
function setup() {
  const server = { retention: { keep_latest: null as number | null, revision: 0 }, resource: { ...resource }, versions: [version(v2, 2), version(v1, 1)],
    documents: new Map<string, object>([[v1, structuredClone(corpus)], [v2, structuredClone(corpus)]]),
    listError: false, previewError: false, restoreError: false, restoreCode: "quota_exceeded", loadRestoredError: false, wrongPreview: false };
  const changed = vi.fn();
  const writes: Request[] = [];
  const results = new Map<string, object>();
  async function handle(request: Request): Promise<Response> {
    const path = new URL(request.url).pathname;
    if (path.endsWith("/editing-lease")) return leaseResponse(request);
    if (path.endsWith("/fields")) return Response.json({ source_version_id: server.resource.current_version_id, status: "not_started", snapshot: null });
    if (path.endsWith("/versions")) return server.listError ? failure() : Response.json({ retention: server.retention, items: server.versions, current_version_id: server.resource.current_version_id, next_before: null });
    if (path.endsWith("/restore")) {
      writes.push(request);
      if (server.restoreError) return failure(server.restoreCode, 409);
      const key = request.headers.get("Idempotency-Key")!;
      if (results.has(key)) return Response.json(results.get(key), { status: 201 });
      const selected = path.split("/").at(-2)!;
      server.documents.set(v3, structuredClone(server.documents.get(selected)!));
      server.versions = [{ ...version(v3, 3), is_current: true, parent_version_id: v2, restored_from_version_id: selected, restored_from_number: selected === v1 ? 1 : 2 }, ...server.versions.map(item => ({ ...item, is_current: false }))];
      server.resource.current_version_id = v3;
      const result = { resource: { ...server.resource }, saved_version_id: v3 };
      results.set(key, result); return Response.json(result, { status: 201 });
    }
    if (path.includes("/versions/") && path.endsWith("/content")) {
      const selected = path.split("/").at(-2)!;
      if (server.previewError || (selected === v3 && server.loadRestoredError)) return failure();
      return Response.json({ version: server.wrongPreview ? version(v3, 3) : server.versions.find(item => item.id === selected), document: server.documents.get(selected) });
    }
    if (path.endsWith("/content")) return Response.json({ resource: server.resource, document: server.documents.get(server.resource.current_version_id) });
    return Response.json(server.resource);
  }
  const fetcher = vi.fn(handle); vi.stubGlobal("fetch", fetcher);
  function Host() {
    const [dirty, setDirty] = useState(false);
    return <Workspace identity={id} csrfToken="csrf" dirty={dirty} onDirty={setDirty} onChanged={changed} />;
  }
  const view = render(<StrictMode><I18nextProvider i18n={i18n}><Host /></I18nextProvider></StrictMode>);
  return { ...view, server, writes, fetcher, handle, changed };
}
async function ready() { await screen.findByText("Editing enabled."); return screen.getByRole("textbox", { name: "Editable document" }); }
const field = () => screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0];
async function open() {
  fireEvent.click(screen.getByRole("button", { name: "Version history" }));
  await screen.findByRole("textbox", { name: "Read-only historical document" });
  return screen.getByRole("region", { name: "Version history" });
}
beforeEach(async () => {
  await setLanguage("en");
  vi.spyOn(window, "confirm").mockReturnValue(true);
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("history preserves live draft, proposed title and undo across read-only previews and language changes", async () => {
  const state = setup(), editor = await ready();
  fireEvent.change(field(), { target: { value: "Незбережена Ґанна" } });
  fireEvent.click(screen.getByText("Workspace settings"));
  fireEvent.change(screen.getByRole("textbox", { name: "Title" }), { target: { value: "Назва чернетки" } });
  const history = await open();
  expect(within(history).getByText(/Your unsaved draft remains/)).toBeVisible();
  expect(within(history).getAllByText("1.54 MB")).toHaveLength(2);
  fireEvent.click(within(history).getByRole("button", { name: /^Version 1/ }));
  await screen.findByRole("heading", { name: /^Version 1$/ });
  const preview = await screen.findByRole("textbox", { name: "Read-only historical document" });
  expect(preview).toHaveAttribute("contenteditable", "false"); expect(preview).toHaveAttribute("aria-readonly", "true");
  expect(preview).not.toHaveTextContent("Незбережена Ґанна");
  fireEvent.keyDown(preview, { key: "z", ctrlKey: true });
  fireEvent.click(screen.getByText("Saved fields"));
  expect(within(history).getAllByText("ПІБ клієнта").length).toBeGreaterThan(0);
  expect(editor.isConnected).toBe(true); expect(editor).not.toBeVisible();
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("textbox", { name: "Історична версія документа лише для читання" })).toBe(preview);
  fireEvent.click(screen.getByRole("button", { name: "Повернутися до редагування" }));
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  expect(editor).toHaveTextContent("Незбережена Ґанна");
  expect(screen.getByRole("textbox", { name: "Назва" })).toHaveValue("Назва чернетки");
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));
  expect(editor).not.toHaveTextContent("Незбережена Ґанна"); expect(state.writes).toHaveLength(0);
});

test("cancelled restore and quota rejection retain the draft; successful restore loads and replaces it once", async () => {
  const state = setup(), editor = await ready();
  fireEvent.change(field(), { target: { value: "Залишити чернетку" } });
  await open();
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  fireEvent.click(screen.getByRole("button", { name: "Restore as a new revision" }));
  expect(state.writes).toHaveLength(0);
  state.server.restoreError = true;
  fireEvent.click(screen.getByRole("button", { name: "Restore as a new revision" }));
  await screen.findByText(/storage allowance/i);
  expect(editor).toHaveTextContent("Залишити чернетку"); expect(state.changed).not.toHaveBeenCalled();
  state.server.restoreError = false;
  fireEvent.click(screen.getByRole("button", { name: "Restore as a new revision" }));
  await waitFor(() => expect(state.changed).toHaveBeenCalledTimes(1));
  expect(editor.isConnected).toBe(false);
  expect(await ready()).not.toHaveTextContent("Залишити чернетку");
  expect(screen.getByRole("button", { name: "Save document" })).toBeDisabled();
  expect(state.writes[1].headers.get("Idempotency-Key")).not.toBe(state.writes[0].headers.get("Idempotency-Key"));
  const history = await open();
  expect(within(history).getByText("Restored from version 2")).toBeVisible();
});

test("committed restore with failed load preserves draft and exact retry across closing history and locale", async () => {
  const state = setup(), editor = await ready();
  fireEvent.change(field(), { target: { value: "Не втрачати Їжака" } });
  await open(); state.server.loadRestoredError = true;
  fireEvent.click(screen.getByRole("button", { name: "Restore as a new revision" }));
  await screen.findByText(/editor could not load it/);
  expect(state.changed).not.toHaveBeenCalled(); expect(editor.isConnected).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Return to editing" }));
  expect(editor).toHaveTextContent("Не втрачати Їжака");
  await act(() => setLanguage("uk"));
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  fireEvent.click(screen.getByRole("button", { name: "Повторити відновлення версії 2" }));
  expect(state.writes).toHaveLength(1);
  state.server.loadRestoredError = false;
  fireEvent.click(screen.getByRole("button", { name: "Повторити відновлення версії 2" }));
  await waitFor(() => expect(state.changed).toHaveBeenCalledTimes(1));
  expect(state.writes[1].headers.get("Idempotency-Key")).toBe(state.writes[0].headers.get("Idempotency-Key"));
  expect(await state.writes[1].clone().json()).toEqual(await state.writes[0].clone().json());
  expect(editor.isConnected).toBe(false);
});

test("list and preview failures retry independently, wrong preview is rejected, and stale current never rebases draft", async () => {
  const state = setup(), editor = await ready();
  fireEvent.change(field(), { target: { value: "Локальний Їжак" } });
  state.server.listError = true; state.server.previewError = true;
  fireEvent.click(screen.getByRole("button", { name: "Version history" }));
  await screen.findByRole("button", { name: "Retry preview" });
  state.server.listError = false;
  fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
  await screen.findByRole("button", { name: /^Version 1/ });
  state.server.previewError = false; state.server.wrongPreview = true;
  fireEvent.click(screen.getByRole("button", { name: "Retry preview" }));
  await screen.findByText("The selected saved revision could not be verified. Refresh history and retry the preview.");
  expect(screen.queryByRole("textbox", { name: "Read-only historical document" })).not.toBeInTheDocument();
  state.server.wrongPreview = false;
  fireEvent.click(screen.getByRole("button", { name: "Retry preview" }));
  await screen.findByRole("textbox", { name: "Read-only historical document" });
  state.server.resource.current_version_id = v3;
  fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
  await screen.findByText(/current revision changed in another session/);
  expect(screen.getByRole("button", { name: "Restore as a new revision" })).toBeDisabled();
  expect(editor).toHaveTextContent("Локальний Їжак");
  vi.mocked(window.confirm).mockReturnValueOnce(false);
  fireEvent.click(within(screen.getByRole("region", { name: "Version history" })).getByRole("button", { name: "Reopen saved document" }));
  expect(editor.isConnected).toBe(true);
});


test.each(["operation_in_progress", "operation_aborted", "upload_busy", "file_too_large"])("restore %s has recovery copy in both languages", async code => {
  const state = setup(); await ready();
  await open(); state.server.restoreError = true; state.server.restoreCode = code;
  fireEvent.click(screen.getByRole("button", { name: "Restore as a new revision" }));
  await screen.findByText(i18n.t(`history.${code}`));
  expect(screen.queryByText(i18n.t(`errors.${code}`))).not.toBeInTheDocument();
  await act(() => setLanguage("uk"));
  expect(screen.getByText(i18n.t(`history.${code}`))).toBeVisible();
});


test.each([1, 2, 5, 1000])("retention policy refresh shows localized limits %s without changing the live draft", async count => {
  const state = setup(), editor = await ready();
  fireEvent.change(field(), { target: { value: "Чернетка Ґанни" } });
  await open();
  await screen.findByText("All saved revisions are retained and count toward storage usage.");
  state.server.retention = { keep_latest: count, revision: 1 };
  fireEvent.click(screen.getByRole("button", { name: "Refresh history" }));
  const number = new Intl.NumberFormat("en").format(count);
  await screen.findByText(`The original and the latest ${number} ${count === 1 ? "revision" : "revisions"} are kept. Older revisions may be permanently removed. Retained files count toward storage usage.`);
  await act(() => setLanguage("uk"));
  const amount = new Intl.NumberFormat("uk-UA").format(count);
  const phrase = count === 1 ? `остання ${amount} версія` : count === 2 ? `останні ${amount} версії` : `останні ${amount} версій`;
  expect(screen.getByText(`Зберігаються оригінал і ${phrase}. Старіші версії можуть бути видалені назавжди. Збережені файли враховуються у використаному сховищі.`, { normalizer: text => text })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Повернутися до редагування" }));
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  expect(editor).toHaveTextContent("Чернетка Ґанни");
  expect(state.writes).toHaveLength(0);
});
