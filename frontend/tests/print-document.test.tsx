import { StrictMode, useState } from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import { leaseResponse } from "./lease-response";

vi.mock("../src/workspace/printView", () => ({ printDocumentNode: vi.fn(() => true) }));
import { printDocumentNode } from "../src/workspace/printView";
const printMock = vi.mocked(printDocumentNode);

const id = "11111111-1111-4111-8111-111111111111";
const v1 = "22222222-2222-4222-8222-222222222222";
const v2 = "44444444-4444-4444-8444-444444444444";
const resource = { id, kind: "document", title: "Заява Їжака", original_filename: "Їжак.docx", current_version_id: v1,
  created_at: "2026-09-07", updated_at: "2026-09-07", size_bytes: 123, digest: "hash", unsupported_count: 0, deletion_pending: false, processing_status: "not_started" };

function setup(save?: (request: Request) => Promise<Response>) {
  const server = { resource: { ...resource }, document: structuredClone(corpus) as object, presentation: { section: {} }, count: 1 };
  const writes = vi.fn(save ?? (async request => {
    const body = await request.clone().json();
    expect(body.source_version_id).toBe(server.resource.current_version_id);
    server.document = body.document;
    server.resource = { ...server.resource, current_version_id: ++server.count === 2 ? v2 : server.resource.current_version_id };
    return Response.json({ resource: server.resource, saved_version_id: server.resource.current_version_id,
      saved_number: server.count, saved_at: "2026-09-07", saved_size_bytes: 456, saved_digest: "saved" }, { status: 201 });
  }));
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path.endsWith("/versions")) return writes(request);
    if (path.endsWith("/editing-lease")) return leaseResponse(request);
    if (path.endsWith("/content")) return Response.json(server);
    if (path.endsWith("/fields")) return Response.json({ source_version_id: server.resource.current_version_id, status: "not_started", snapshot: null });
    if (request.method === "PATCH") { server.resource.title = (await request.json()).title; return Response.json(server.resource); }
    return Response.json(server.resource);
  }));
  function Host() {
    const [dirty, setDirty] = useState(false);
    return <Workspace identity={id} csrfToken="csrf" dirty={dirty} onDirty={setDirty} />;
  }
  const view = render(<StrictMode><I18nextProvider i18n={i18n}><Host /></I18nextProvider></StrictMode>);
  return { ...view, server, writes };
}
async function ready() {
  await screen.findByText("Editing enabled.");
  return screen.getByRole("textbox", { name: "Editable document" });
}
const printButton = () => screen.getByRole("button", { name: "Print" });
const sidebarField = () => screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0];

beforeEach(async () => {
  await setLanguage("en");
  printMock.mockClear();
  printMock.mockReturnValue(true);
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("a clean document prints the rendered canvas alone without creating a revision", async () => {
  const state = setup();
  await ready();
  fireEvent.click(printButton());
  await waitFor(() => expect(printMock).toHaveBeenCalledTimes(1));
  const [node, layout] = printMock.mock.calls[0];
  expect(node?.classList.contains("ProseMirror")).toBe(true);
  expect(layout.rules).toContain("[data-layout=");
  expect(layout.scope).toBeTruthy();
  expect(state.writes).not.toHaveBeenCalled();
  expect(screen.queryByText(/print dialog could not be opened/i)).toBeNull();
});

test("unsaved work is saved before printing", async () => {
  const state = setup();
  await ready();
  fireEvent.change(sidebarField(), { target: { value: "Єва Ковальчук" } });
  fireEvent.click(printButton());
  await waitFor(() => expect(printMock).toHaveBeenCalledTimes(1));
  expect(state.writes).toHaveBeenCalledTimes(1);
  expect(state.server.resource.current_version_id).toBe(v2);
});

test("a failed pre-save aborts printing and shows the save error instead", async () => {
  setup(async () => Response.json({ error: { code: "quota_exceeded", parameters: {} } }, { status: 422 }));
  await ready();
  fireEvent.change(sidebarField(), { target: { value: "Єва Ковальчук" } });
  fireEvent.click(printButton());
  await screen.findByText("There is not enough storage allowance to save this file.");
  expect(printMock).not.toHaveBeenCalled();
  expect(screen.queryByText(/print dialog could not be opened/i)).toBeNull();
});

test("unavailable printing suggests saving the file locally beside a download action", async () => {
  printMock.mockReturnValue(false);
  setup();
  await ready();
  fireEvent.click(printButton());
  await screen.findByText("The browser print dialog could not be opened. Save the document locally and print it from the file.");
  const fallback = screen.getByText(/print dialog could not be opened/i).closest(".workspace-print-fallback") as HTMLElement;
  expect(within(fallback).getByRole("button", { name: "Download saved DOCX" })).toBeEnabled();
  expect(printMock).toHaveBeenCalledTimes(1);
});
