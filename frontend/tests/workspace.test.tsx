import { leaseResponse } from "./lease-response";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { App } from "../src/App";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

const id = "11111111-1111-4111-8111-111111111111";
const second = "22222222-2222-4222-8222-222222222222";
const resource = { id, kind: "template", title: "Заява Ґанни", original_filename: "Заява.docx", current_version_id: "v1", created_at: "2026-09-06", updated_at: "2026-09-06", size_bytes: 3, digest: "hash", unsupported_count: 1, deletion_pending: false, processing_status: "not_started" };
const session = { csrf_token: "csrf", user: { id: "owner", login: "owner@example.test", display_name: "Ґанна", role: "user", ui_language: "uk" } };
function defaults(request: Request | string) {
  const path = new URL(typeof request === "string" ? request : request.url, window.location.origin).pathname;
  if (path.endsWith("/editing-lease")) return leaseResponse(request as Request);
  if (path.endsWith("/content")) return Response.json({ resource, document: corpus });
  if (path.endsWith("/session")) return Response.json(session);
  if (path === "/api/documents") return Response.json({ items: [resource, { ...resource, id: second, title: "Інша заява" }], next_cursor: null });
  if (path.endsWith("/usage")) return Response.json({ used_bytes: 3, reserved_bytes: 0, limit_bytes: 1000, available_bytes: 997, over_limit: false });
  return Response.json({ status: "ok" });
}
beforeEach(async () => { await setLanguage("uk"); window.history.replaceState(null, "", `/editor/${id}`); });
function show() { return render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>); }

test("direct workspace opens a verified model, preserves the live editor across profile/language navigation, and guards discards", async () => {
  const fetcher = vi.fn(async (request: Request | string) => defaults(request));
  vi.stubGlobal("fetch", fetcher);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  show();
  await screen.findByRole("heading", { name: resource.title });
  const editor = await screen.findByRole("textbox", { name: "Редагований документ" });
  await screen.findByText("Редагування дозволено.");
  const field = (await screen.findAllByRole("textbox", { name: /^Значення поля:/ }))[0];
  fireEvent.change(field, { target: { value: "Незбережений Їжак" } });
  expect(await screen.findByText(/Є незбережені зміни/)).toBeVisible();
  fireEvent.click(screen.getByRole("link", { name: "Профіль" }));
  await act(() => setLanguage("en"));
  fireEvent.click(screen.getByRole("link", { name: "Document workspace" }));
  expect(screen.getByRole("textbox", { name: "Editable document" })).toBe(editor);
  expect(editor).toHaveTextContent("Незбережений Їжак");
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(confirm).toHaveBeenCalled();
  expect(fetcher.mock.calls.some(([request]) => typeof request !== "string" && new URL(request.url).pathname === "/api/auth/logout")).toBe(false);
  fireEvent.click(screen.getByRole("link", { name: "My documents" }));
  // The section link preselects the documents tab, so the gallery refetches.
  const otherCard = await screen.findByRole("article", { name: "Інша заява" });
  const openLink = within(otherCard).getByRole("link", { name: "Інша заява" });
  fireEvent.click(openLink);
  expect(window.location.pathname).toBe("/documents");
  confirm.mockReturnValue(true);
  fireEvent.click(openLink);
  await waitFor(() => expect(window.location.pathname).toBe(`/editor/${second}`));
  expect(await screen.findByText("Saved revision opened.")).toBeVisible();
  expect(await screen.findByRole("textbox", { name: "Editable document" })).not.toBe(editor);
});

test("history cannot replace a dirty workspace without consent", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request | string) => defaults(request)));
  vi.spyOn(window, "confirm").mockReturnValue(false); show();
  await screen.findByRole("heading", { name: resource.title });
  await screen.findByText("Редагування дозволено.");
  const field = (await screen.findAllByRole("textbox", { name: /^Значення поля:/ }))[0];
  fireEvent.change(field, { target: { value: "Чернетка" } });
  act(() => { window.history.pushState(null, "", `/editor/${second}`); window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(window.location.pathname).toBe(`/editor/${id}`);
  expect(screen.getByRole("textbox", { name: "Редагований документ" })).toHaveTextContent("Чернетка");
});

test("opening errors retry without a fake editor and stale responses are ignored after unmount", async () => {
  let finish!: (response: Response) => void;
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ error: { code: "not_found" } }, { status: 404 }))
    .mockRejectedValueOnce(new Error("offline"))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  const view = render(<I18nextProvider i18n={i18n}><Workspace csrfToken="csrf" identity={id} dirty={false} onDirty={vi.fn()} /></I18nextProvider>);
  await screen.findByRole("alert");
  expect(screen.queryByRole("textbox")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Повторити відкриття" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Повторити відкриття" }));
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  view.unmount(); await act(async () => finish(Response.json({ resource, document: corpus })));
  expect(screen.queryByRole("textbox")).toBeNull();
});
