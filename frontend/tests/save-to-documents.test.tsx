import { StrictMode, useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import { leaseResponse } from "./lease-response";

const id = "11111111-1111-4111-8111-111111111111";
const v1 = "22222222-2222-4222-8222-222222222222";
const v2 = "44444444-4444-4444-8444-444444444444";
const createdId = "66666666-6666-4666-8666-666666666666";
const resource = { id, kind: "template", title: "Заява Їжака", original_filename: "Їжак.docx", current_version_id: v1,
  created_at: "2026-09-07", updated_at: "2026-09-07", size_bytes: 123, digest: "hash", unsupported_count: 0, deletion_pending: false, processing_status: "not_started" };
const created = { ...resource, id: createdId, kind: "document", title: "Нова заява", current_version_id: v1 };
const failure = (code: string, status = 409) => Response.json({ error: { code, parameters: {} } }, { status });

function setup({ kind = "template", copies }: { kind?: string; copies?: (request: Request, attempt: number) => Promise<Response> } = {}) {
  const server = { resource: { ...resource, kind }, document: structuredClone(corpus) as object, count: 1 };
  const copiesRequests: Request[] = [];
  const writes = vi.fn(async (request: Request) => {
    const body = await request.clone().json();
    expect(body.source_version_id).toBe(server.resource.current_version_id);
    server.document = body.document;
    server.resource = { ...server.resource, current_version_id: ++server.count === 2 ? v2 : server.resource.current_version_id };
    return Response.json({ resource: server.resource, saved_version_id: server.resource.current_version_id,
      saved_number: server.count, saved_at: "2026-09-07", saved_size_bytes: 456, saved_digest: "saved" }, { status: 201 });
  });
  let copyAttempt = 0;
  const copiesHandler = vi.fn(async (request: Request) => {
    copyAttempt += 1;
    copiesRequests.push(request);
    return copies ? copies(request, copyAttempt) : Response.json(created, { status: 201 });
  });
  const opened = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path.endsWith("/versions")) return writes(request);
    if (path.endsWith("/copies")) return copiesHandler(request);
    if (path.endsWith("/editing-lease")) return leaseResponse(request);
    if (path.endsWith("/content")) return Response.json(server);
    if (path.endsWith("/fields")) return Response.json({ source_version_id: server.resource.current_version_id, status: "not_started", snapshot: null });
    if (request.method === "PATCH") { server.resource.title = (await request.json()).title; return Response.json(server.resource); }
    return Response.json(server.resource);
  }));
  function Host({ onOpenResource }: { onOpenResource?: (identity: string) => void }) {
    const [dirty, setDirty] = useState(false);
    return <Workspace identity={id} csrfToken="csrf" dirty={dirty} onDirty={setDirty} onOpenResource={onOpenResource} />;
  }
  const view = render(<StrictMode><I18nextProvider i18n={i18n}><Host onOpenResource={opened} /></I18nextProvider></StrictMode>);
  const rerenderWithoutOpen = () => view.rerender(<StrictMode><I18nextProvider i18n={i18n}><Host /></I18nextProvider></StrictMode>);
  return { ...view, server, writes, copiesHandler, copiesRequests, opened, rerenderWithoutOpen };
}
async function ready(kind = "template") {
  await screen.findByText("Editing enabled.");
  expect(screen.getByText(kind === "template" ? "Editing a template" : "Individual document")).toBeVisible();
  return screen.getByRole("textbox", { name: "Editable document" });
}
const saveToDocuments = () => screen.getByRole("button", { name: "Save to documents" });
const openPrompt = () => fireEvent.click(saveToDocuments());
const nameInput = () => screen.getByRole("textbox", { name: "New document title" });
const confirm = () => screen.getByRole("button", { name: "Create document" });
const sidebarField = () => screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0];

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("only template workspaces offer save-to-documents; the prompt defaults to the template title", async () => {
  const state = setup();
  await ready();
  expect(saveToDocuments()).toBeEnabled();
  openPrompt();
  expect(screen.getByText(/The template draft is saved first/)).toBeVisible();
  expect(nameInput()).toHaveValue("Заява Їжака — [Введіть ПІБ клієнта]");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("button", { name: "Create document" })).toBeNull();
  expect(state.copiesHandler).not.toHaveBeenCalled();
});

test("the default name appends the first filled field value from the mounted editor", async () => {
  setup();
  await ready();
  fireEvent.change(sidebarField(), { target: { value: "  Єва\tКовальчук " } });
  openPrompt();
  expect(nameInput()).toHaveValue("Заява Їжака — Єва Ковальчук");
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
});

test("a clean template copies its saved revision without a redundant save and offers the guarded open", async () => {
  const state = setup();
  await ready();
  openPrompt();
  fireEvent.change(nameInput(), { target: { value: "Нова заява" } });
  fireEvent.click(confirm());
  await screen.findByText(/Document “Нова заява” was created in the Documents tab./);
  expect(state.writes).not.toHaveBeenCalled();
  expect(state.copiesHandler).toHaveBeenCalledTimes(1);
  expect(await state.copiesRequests[0].clone().json()).toMatchObject({ title: "Нова заява", source_version_id: v1 });
  expect(state.copiesRequests[0].headers.get("X-CSRF-Token")).toBe("csrf");
  fireEvent.click(screen.getByRole("button", { name: "Open document" }));
  expect(state.opened).toHaveBeenCalledWith(createdId);
  expect(state.copiesHandler.mock.calls.length).toBe(1);
});

test("a dirty template is saved first and the copy snapshots the newly saved revision", async () => {
  const state = setup();
  await ready();
  fireEvent.change(sidebarField(), { target: { value: "Єва Ковальчук" } });
  openPrompt();
  fireEvent.click(confirm());
  await screen.findByText(/Document “Нова заява” was created in the Documents tab./);
  await waitFor(() => expect(state.writes).toHaveBeenCalledTimes(1));
  expect(state.copiesHandler).toHaveBeenCalledTimes(1);
  expect(await state.copiesRequests[0].clone().json()).toMatchObject({ title: "Заява Їжака — Єва Ковальчук", source_version_id: v2 });
});

test("a failed pre-save aborts the copy and keeps the prompt", async () => {
  const state = setup({ copies: async () => Response.json(created, { status: 201 }) });
  state.writes.mockImplementation(async () => failure("quota_exceeded", 422));
  await ready();
  fireEvent.change(sidebarField(), { target: { value: "Єва Ковальчук" } });
  openPrompt();
  fireEvent.click(confirm());
  await screen.findByText("There is not enough storage allowance to save this file.");
  expect(state.copiesHandler).not.toHaveBeenCalled();
  expect(confirm()).toBeEnabled();
  expect(screen.queryByText(/was created in the Documents tab/)).toBeNull();
});

test("definitive copy failures show a localized error and retry with a fresh idempotency key", async () => {
  const state = setup({ copies: (request, attempt) => attempt === 1 ? Promise.resolve(failure("quota_exceeded", 422)) : Promise.resolve(Response.json(created, { status: 201 })) });
  await ready();
  openPrompt();
  fireEvent.click(confirm());
  await screen.findByText("There is not enough storage allowance to save this file.");
  expect(state.writes).not.toHaveBeenCalled();
  fireEvent.click(confirm());
  await screen.findByText(/Document “Нова заява” was created in the Documents tab./);
  expect(state.copiesHandler).toHaveBeenCalledTimes(2);
  expect(state.copiesRequests[1].headers.get("Idempotency-Key")).not.toBe(state.copiesRequests[0].headers.get("Idempotency-Key"));
});

test("the open action is omitted when no cross-resource navigation is available", async () => {
  const state = setup();
  await ready();
  state.rerenderWithoutOpen();
  openPrompt();
  fireEvent.click(confirm());
  await screen.findByText(/Document “Нова заява” was created in the Documents tab./);
  expect(screen.queryByRole("button", { name: "Open document" })).toBeNull();
});

test("document workspaces offer no save-to-documents action", async () => {
  setup({ kind: "document" });
  await ready("document");
  expect(screen.queryByRole("button", { name: "Save to documents" })).toBeNull();
});
