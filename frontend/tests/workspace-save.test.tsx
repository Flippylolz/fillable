import { StrictMode, useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import { leaseResponse } from "./lease-response";

const id = "11111111-1111-4111-8111-111111111111";
const v1 = "22222222-2222-4222-8222-222222222222";
const v2 = "44444444-4444-4444-8444-444444444444";
const v3 = "55555555-5555-4555-8555-555555555555";
const resource = { id, kind: "document", title: "Заява Їжака", original_filename: "Їжак.docx", current_version_id: v1,
  created_at: "2026-09-07", updated_at: "2026-09-07", size_bytes: 123, digest: "hash", unsupported_count: 1, deletion_pending: false, processing_status: "not_started" };
const failure = (code: string, reason?: string, status = 409) => Response.json({ error: { code, parameters: { reason } } }, { status });
function setup(write?: (request: Request) => Promise<Response>) {
  const server = { resource: { ...resource }, document: structuredClone(corpus) as object, count: 1 };
  const leases: { client_id: string; source_version_id: string; action: string }[] = [];
  const changed = vi.fn(), busy = vi.fn();
  async function commit(request: Request) {
    const body = await request.clone().json();
    expect(body.source_version_id).toBe(server.resource.current_version_id);
    server.document = body.document;
    server.resource = { ...server.resource, current_version_id: ++server.count === 2 ? v2 : v3 };
    return Response.json({ resource: server.resource, saved_version_id: server.resource.current_version_id, saved_number: server.count,
      saved_at: "2026-09-07", saved_size_bytes: 456, saved_digest: "saved" }, { status: 201 });
  }
  const writes = vi.fn(write ?? commit);
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path.endsWith("/versions")) return writes(request);
    if (path.endsWith("/editing-lease")) { leases.push(await request.clone().json()); return leaseResponse(request); }
    if (path.endsWith("/content")) return Response.json(server);
    if (path.endsWith("/fields")) return Response.json({ source_version_id: server.resource.current_version_id, status: "not_started", snapshot: null });
    if (request.method === "PATCH") { server.resource.title = (await request.json()).title; return Response.json(server.resource); }
    return Response.json(server.resource);
  }));
  let pause!: (value: boolean) => void;
  function Host() {
    const [operationsPaused, setOperationsPaused] = useState(false); pause = setOperationsPaused;
    const [dirty, setDirty] = useState(false);
    return <Workspace identity={id} csrfToken="csrf" dirty={dirty} onDirty={setDirty} onChanged={changed} onBusy={busy} operationsPaused={operationsPaused} />;
  }
  const view = render(<StrictMode><I18nextProvider i18n={i18n}><Host /></I18nextProvider></StrictMode>);
  return { ...view, server, writes, commit, leases, changed, busy, pause: (value: boolean) => pause(value) };
}
async function ready() { await screen.findByText("Editing enabled."); return screen.getByRole("textbox", { name: "Editable document" }); }
const field = () => screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0];
const save = () => screen.getByRole("button", { name: "Save document" });
const change = (text: string) => fireEvent.change(field(), { target: { value: text } });
beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("late acknowledgment preserves newer edits, proposed title, stable lease client and undo across locale", async () => {
  let finish!: (response: Response) => void;
  const state = setup(() => new Promise(resolve => { finish = resolve; }));
  const editor = await ready(); expect(save()).toBeDisabled();
  change("Перша версія Ґанни"); fireEvent.click(save());
  await waitFor(() => expect(state.writes).toHaveBeenCalledTimes(1));
  const sent = state.writes.mock.calls[0][0];
  expect(sent.headers.get("X-CSRF-Token")).toBe("csrf");
  change("Новіший Їжак 🙂");
  fireEvent.click(screen.getByText("Workspace settings"));
  fireEvent.change(screen.getByRole("textbox", { name: "Title" }), { target: { value: "Незбережена назва" } });
  expect(screen.getByRole("button", { name: "Rename" })).toBeDisabled();
  await act(async () => finish(await state.commit(sent)));
  await ready(); expect(editor).toHaveTextContent("Новіший Їжак 🙂");
  expect(screen.getByText(/You have unsaved changes/)).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Незбережена назва");
  expect(new Set(state.leases.map(item => item.client_id)).size).toBe(1);
  expect(state.leases.some(item => item.action === "acquire" && item.source_version_id === v2)).toBe(true);
  state.writes.mockImplementation(state.commit);
  fireEvent.click(save()); await waitFor(() => expect(state.changed).toHaveBeenCalledTimes(2));
  await ready(); expect(save()).toBeDisabled();
  expect(screen.getByText(/You have unsaved changes/)).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Rename" }));
  await screen.findByText("All document changes saved.");
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toBe(editor);
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));
  expect(screen.getByText(/Є незбережені зміни/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Зберегти документ" })).toBeEnabled();
});

test("lost committed response retries the exact earlier snapshot while access is paused and newer edits remain", async () => {
  const state = setup(); const editor = await ready();
  let committed!: Response;
  state.writes.mockImplementationOnce(async request => { committed = await state.commit(request); throw new Error("lost response"); });
  change("Збережений Ґудзик"); fireEvent.click(save());
  await screen.findByText(/The save result is not confirmed/);
  change("Пізніша чернетка Їжака");
  fireEvent(window, new Event("pagehide"));
  await screen.findByText("Editing is paused. Your draft is kept in this workspace.");
  state.writes.mockResolvedValueOnce(committed);
  fireEvent.click(screen.getByRole("button", { name: "Retry save" }));
  await waitFor(() => expect(state.changed).toHaveBeenCalledTimes(1));
  expect(await state.writes.mock.calls[1][0].clone().json()).toEqual(await state.writes.mock.calls[0][0].clone().json());
  expect(state.writes.mock.calls[1][0].headers.get("Idempotency-Key")).toBe(state.writes.mock.calls[0][0].headers.get("Idempotency-Key"));
  expect(editor).toHaveTextContent("Пізніша чернетка Їжака"); expect(screen.getByText(/You have unsaved changes/)).toBeVisible();
  await ready(); fireEvent.click(save()); await screen.findByText("All document changes saved.");
  expect(state.server.count).toBe(3);
});

test("an older replay never adopts a newer server revision as the base of the old draft; reopen is explicit", async () => {
  const state = setup(async () => Response.json({ resource: { ...resource, current_version_id: v3 }, saved_version_id: v2 }));
  const editor = await ready(); change("Збережіть мою чернетку"); fireEvent.click(save());
  await screen.findByText(/The saved revision changed. Your draft/);
  expect(save()).toBeDisabled(); expect(editor).toHaveTextContent("Збережіть мою чернетку");
  expect(state.changed).not.toHaveBeenCalled();
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  const reopen = within(state.container.querySelector(".workspace-save-error") as HTMLElement).getByRole("button", { name: "Reopen saved document" });
  fireEvent.click(reopen); expect(editor.isConnected).toBe(true);
  state.server.resource.current_version_id = v3;
  confirm.mockReturnValue(true); fireEvent.click(reopen);
  await screen.findByText("Saved revision opened.");
  expect(await ready()).not.toBe(editor); expect(save()).toBeDisabled();
});

test.each(["quota_exceeded", "operation_aborted", "file_too_large", "upload_timeout", "upload_busy", "invalid_document"])("definite %s failure keeps draft and permits a new operation", async code => {
  const state = setup(async () => failure(code)); const editor = await ready();
  change("Чернетка Ґанни"); fireEvent.click(save());
  await waitFor(() => expect(state.container.querySelector(".workspace-save-error")).not.toBeNull());
  expect(state.container.querySelector(".workspace-save-error")).not.toHaveTextContent(/upload/i);
  expect(editor).toHaveTextContent("Чернетка Ґанни"); expect(save()).toBeEnabled();
  expect(screen.queryByText("All document changes saved.")).toBeNull();
  state.writes.mockImplementation(state.commit); fireEvent.click(save());
  await screen.findByText("All document changes saved.");
  expect(state.writes.mock.calls[1][0].headers.get("Idempotency-Key")).not.toBe(state.writes.mock.calls[0][0].headers.get("Idempotency-Key"));
});

test("invalid values and native composition disable new saves, while uncertain reopen warns before discard", async () => {
  const state = setup(async () => failure("storage_unavailable", undefined, 503)); const editor = await ready();
  change("🙂".repeat(65537)); expect(save()).toBeDisabled();
  change("Чернетка"); fireEvent.compositionStart(editor); expect(save()).toBeDisabled();
  fireEvent.compositionEnd(editor); await waitFor(() => expect(save()).toBeEnabled());
  fireEvent.click(save()); await screen.findByText(/The save result is not confirmed/);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  fireEvent.click(within(state.container.querySelector(".workspace-save-error") as HTMLElement).getByRole("button", { name: "Reopen saved document" }));
  expect(confirm).toHaveBeenCalledWith("The save result is not confirmed. Open the latest saved revision and discard the current draft?");
  expect(editor.isConnected).toBe(true);
});

test("an in-progress save explains the same-attempt retry in both languages", async () => {
  const state = setup(async () => failure("operation_in_progress")); await ready();
  change("Чернетка"); fireEvent.click(save());
  await screen.findByText("This save is still in progress. Retry shortly to check its result.");
  expect(screen.getByRole("button", { name: "Retry save" })).toBeEnabled();
  await act(() => setLanguage("uk"));
  expect(screen.getByText("Це збереження ще триває. Повторіть запит згодом, щоб перевірити результат.")).toBeVisible();
  expect(state.writes).toHaveBeenCalledTimes(1);
});

test("default autosave preserves newer typing after a delayed acknowledgment and saves it against the new version", async () => {
  let finish!: (response: Response) => void;
  const state = setup(request => state.writes.mock.calls.length === 1 ? new Promise(resolve => { finish = resolve; }) : state.commit(request));
  const editor = await ready();
  change("Перша автоматична Ґанна");
  await waitFor(() => expect(state.writes).toHaveBeenCalledTimes(1), { timeout: 4000 });
  const first = state.writes.mock.calls[0][0];
  change("Новіша Єва 🙂");
  await act(async () => finish(await state.commit(first)));
  await waitFor(() => expect(state.writes).toHaveBeenCalledTimes(2), { timeout: 4000 });
  await screen.findByText("All document changes saved.");
  expect(screen.getByRole("textbox", { name: "Editable document" })).toBe(editor);
  expect(editor).toHaveTextContent("Новіша Єва 🙂");
  expect((await state.writes.mock.calls[1][0].clone().json()).source_version_id).toBe(v2);
}, 15000);

test("autosave pauses after a quota failure, keeps newer edits and resumes after explicit save succeeds", async () => {
  const state = setup(request => state.writes.mock.calls.length === 1 ? Promise.resolve(failure("quota_exceeded")) : state.commit(request));
  const editor = await ready(); change("Залишити при помилці");
  await screen.findByText("There is not enough storage allowance to save this file.", {}, { timeout: 4000 });
  expect(screen.getByText("Autosave is paused. Your unsaved changes are kept in this workspace.")).toBeVisible();
  change("Новіша чернетка Ґанни");
  await act(() => new Promise(resolve => setTimeout(resolve, 2300)));
  expect(state.writes).toHaveBeenCalledTimes(1); expect(editor).toHaveTextContent("Новіша чернетка Ґанни");
  fireEvent.click(save()); await screen.findByText("All document changes saved.");
  await waitFor(() => expect(state.leases.at(-1)).toMatchObject({ action: "acquire", source_version_id: v2 }));
  await screen.findByText("Editing enabled.");
  await waitFor(() => expect(field()).toBeEnabled());
  change("Після виправлення Їжак");
  expect(editor).toHaveTextContent("Після виправлення Їжак");
  await waitFor(() => expect(state.writes).toHaveBeenCalledTimes(3), { timeout: 4000 });
  await screen.findByText("All document changes saved.");
  expect(editor).toHaveTextContent("Після виправлення Їжак");
}, 15000);


test("another page's active mutation defers autosave until it completes", async () => {
  const state = setup(); await ready(); change("Чернетка перед зміною профілю");
  await act(() => state.pause(true));
  await act(() => new Promise(resolve => setTimeout(resolve, 2300)));
  expect(state.writes).not.toHaveBeenCalled();
  expect(field()).toHaveValue("Чернетка перед зміною профілю");
  await act(() => state.pause(false));
  await waitFor(() => expect(state.writes).toHaveBeenCalledTimes(1), { timeout: 4000 });
  await screen.findByText("All document changes saved.");
}, 10000);
