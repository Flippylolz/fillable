import { File as NodeFile, Buffer } from "node:buffer";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Library } from "../src/library/Library";
import { App } from "../src/App";
import { SessionPages } from "../src/SessionPages";
import { i18n, setLanguage } from "../src/i18n";

const usage = { used_bytes: 10, reserved_bytes: 2, limit_bytes: 1000, available_bytes: 988, over_limit: false };
const item = { id: "resource", kind: "template", title: "Ґанна <script>", original_filename: "Заява.docx", current_version_id: "version", size_bytes: 10, digest: "a".repeat(64), unsupported_count: 1, processing_status: "not_started", created_at: "2026-09-06T10:00:00Z", updated_at: "2026-09-06T10:00:00Z" };
const session = { csrf_token: "csrf", user: { id: "owner", email: "owner@example.test", display_name: "Ґанна", role: "user", ui_language: "uk" } };
const fail = (code: string) => Response.json({ error: { code, parameters: {} } }, { status: 409 });
const onBusy = vi.fn(); const onDirty = vi.fn(); const onSaved = vi.fn();
const empty = () => Response.json({ items: [], next_cursor: null });
function show(disabled = false) { return render(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={disabled} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} /></I18nextProvider>); }
function file(name = "Заява Ґанни.docx", bytes: BlobPart[] = ["Original Ukrainian bytes: Їжак"]) { return new NodeFile(bytes as ConstructorParameters<typeof NodeFile>[0], name) as unknown as File; }
function choose(value: File) { fireEvent.change(screen.getByLabelText("Файл DOCX"), { target: { files: [value] } }); }
function submit() { fireEvent.submit(screen.getByRole("form", { name: "Завантажити файл DOCX" })); }
function defaults(request: Request) {
  const path = new URL(typeof request === "string" ? request : request.url, window.location.origin).pathname;
  if (path === "/api/storage/usage") return Response.json(usage);
  if (path === "/api/auth/session") return Response.json(session);
  if (path === "/api/health") return Response.json({ status: "ok" });
  return empty();
}
beforeEach(async () => {
  // Match the accepted non-secure browser origin: randomUUID is unavailable.
  vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
  await setLanguage("uk"); window.history.replaceState(null, "", "/"); onBusy.mockClear(); onDirty.mockClear(); onSaved.mockClear();
});

test.each(["operation_aborted", "operation_conflict"])("ambiguous upload retries preserve bytes and key; %s starts a new attempt", async code => {
  let attempt = 0;
  let saved = false;
  const fetcher = vi.fn(async (request: Request) => {
    if (request.method === "POST") {
      attempt++;
      if (attempt === 1) throw new Error("offline");
      if (attempt === 2) return fail(code);
      saved = true; return Response.json({ ...item, kind: "document", title: "Канонічна назва" });
    }
    if (new URL(request.url).pathname === "/api/documents" && saved) return Response.json({ items: [{ ...item, kind: "document", title: "Канонічна назва" }], next_cursor: null });
    return defaults(request);
  });
  vi.stubGlobal("fetch", fetcher);
  show();
  await screen.findByText(/Шаблонів ще немає/);
  const original = file(); choose(original);
  fireEvent.change(screen.getByLabelText("Назва документа"), { target: { value: "Чернетка Їжак" } });
  fireEvent.change(screen.getByLabelText("Зберегти як"), { target: { value: "document" } });
  submit(); await screen.findByRole("alert");
  expect(screen.getByLabelText("Назва документа")).toHaveValue("Чернетка Їжак");
  expect(onSaved).not.toHaveBeenCalled();
  submit(); await waitFor(() => expect(attempt).toBe(2));
  await waitFor(() => expect(screen.getByRole("button", { name: "Завантажити та зберегти" })).toBeEnabled());
  submit();
  expect(await screen.findByText("«Канонічна назва» збережено.")).toBeVisible();
  expect(await screen.findByRole("article", { name: "Канонічна назва" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "Документи" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByLabelText("Назва документа")).toHaveValue("");
  expect(screen.getByLabelText("Файл DOCX")).toHaveValue("");
  expect(onSaved).toHaveBeenCalledTimes(1);
  expect(onDirty).toHaveBeenLastCalledWith(false);
  const posts = fetcher.mock.calls.map(([request]) => request).filter(request => request.method === "POST");
  expect(posts[0].headers.get("idempotency-key")).toBe(posts[1].headers.get("idempotency-key"));
  expect(posts[2].headers.get("idempotency-key")).not.toBe(posts[1].headers.get("idempotency-key"));
  expect(posts[0].headers.get("X-CSRF-Token")).toBe("csrf");
  expect(JSON.parse(Buffer.from(posts[0].headers.get("X-Upload-Metadata")!, "base64").toString())).toEqual({ kind: "document", filename: original.name, title: "Чернетка Їжак" });
  expect(await posts[0].text()).toBe("Original Ukrainian bytes: Їжак");
});

test("client validation and quota failure never claim saved work or discard the draft", async () => {
  const fetcher = vi.fn(async (request: Request) => request.method === "POST" ? fail("quota_exceeded") : defaults(request));
  vi.stubGlobal("fetch", fetcher); show(); await screen.findByText(/Шаблонів ще немає/);
  submit(); expect(await screen.findByRole("alert")).toBeVisible();
  choose(file("legacy.doc")); submit(); expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("errors.unsupported_document"));
  choose(file("large.docx", [new Uint8Array(10 * 1024 * 1024 + 1)])); submit();
  expect(screen.getByRole("alert")).toHaveTextContent(i18n.t("errors.file_too_large"));
  expect(fetcher.mock.calls.filter(([request]) => request.method === "POST")).toHaveLength(0);
  choose(file()); fireEvent.change(screen.getByLabelText("Назва документа"), { target: { value: " " } }); submit();
  expect(fetcher.mock.calls.filter(([request]) => request.method === "POST")).toHaveLength(0);
  fireEvent.change(screen.getByLabelText("Назва документа"), { target: { value: "Спроба" } }); submit();
  expect(await screen.findByRole("alert")).toHaveTextContent(i18n.t("errors.quota_exceeded"));
  expect(screen.getByLabelText("Назва документа")).toHaveValue("Спроба"); expect(onSaved).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Файл DOCX"), { target: { files: [] } });
  expect(screen.getByLabelText("Назва документа")).toHaveValue("");
  expect(onDirty).toHaveBeenLastCalledWith(false);
});

test("list and quota errors retry, cursor failures keep saved rows, and pagination deduplicates", async () => {
  let lists = 0; let quotas = 0; let more = 0;
  const fetcher = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.pathname === "/api/storage/usage") {
      quotas++; if (quotas === 1) throw new Error("offline");
      return Response.json({ ...usage, limit_bytes: 0, available_bytes: 0, over_limit: true });
    }
    if (url.searchParams.has("cursor")) {
      more++; if (more === 1) return fail("dependencies_unavailable");
      if (more === 2) throw new Error("offline");
      return Response.json({ items: [item, { ...item, id: "older", title: "Попередня" }], next_cursor: null });
    }
    lists++; if (lists === 1) return fail("dependencies_unavailable");
    return Response.json({ items: [item], next_cursor: "cursor" });
  });
  vi.stubGlobal("fetch", fetcher); show();
  await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
  fireEvent.click(screen.getByRole("button", { name: "Оновити бібліотеку" }));
  expect(await screen.findByRole("article", { name: item.title })).toBeVisible();
  expect(screen.getByText(/Використання перевищує/)).toBeVisible();
  expect(screen.getByRole("meter")).toHaveAttribute("max", "1");
  expect(document.querySelector("script")).toBeNull();
  for (let attempt = 1; attempt <= 3; attempt++) {
    fireEvent.click(screen.getByRole("button", { name: "Завантажити ще" }));
    await waitFor(() => expect(more).toBe(attempt));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Завантажуємо документи…" })).toBeNull());
    expect(screen.getByRole("article", { name: item.title })).toBeVisible();
  }
  expect(await screen.findByRole("article", { name: "Попередня" })).toBeVisible();
  expect(screen.getAllByRole("article")).toHaveLength(2);
  expect(screen.queryByRole("button", { name: "Завантажити ще" })).toBeNull();
});

test("tab changes ignore old list/usage results, support keyboard tabs, and abort on unmount", async () => {
  const finish: ((response: Response) => void)[] = [];
  const fetcher = vi.fn((request: Request) => {
    if (finish.length < 2) return new Promise<Response>(resolve => finish.push(resolve));
    return Promise.resolve(defaults(request));
  });
  vi.stubGlobal("fetch", fetcher); const view = show();
  await waitFor(() => expect(finish).toHaveLength(2));
  const templates = screen.getByRole("tab", { name: "Шаблони" });
  fireEvent.keyDown(templates, { key: "ArrowRight" });
  expect(await screen.findByText(/Документів ще немає/)).toBeVisible();
  await act(async () => { finish[0](Response.json({ items: [item] })); finish[1](Response.json({ ...usage, used_bytes: 999 })); });
  expect(screen.queryByRole("article")).toBeNull();
  expect(screen.queryByText(/999/)).toBeNull();
  fireEvent.keyDown(screen.getByRole("tab", { name: "Документи" }), { key: "Home" });
  await screen.findByText(/Шаблонів ще немає/);
  fireEvent.keyDown(templates, { key: "End" });
  await screen.findByText(/Документів ще немає/);
  fireEvent.keyDown(screen.getByRole("tab", { name: "Документи" }), { key: "Tab" });
  expect(screen.getByRole("tab", { name: "Документи" })).toHaveAttribute("aria-selected", "true");
  view.unmount();
  expect(fetcher.mock.calls.every(([request]) => request.signal.aborted)).toBe(true);
});

test("pending uploads block duplicate submits and late success cannot revive unmounted state", async () => {
  let finish!: (response: Response) => void;
  const fetcher = vi.fn((request: Request) => request.method === "POST" ? new Promise<Response>(resolve => { finish = resolve; }) : Promise.resolve(defaults(request)));
  vi.stubGlobal("fetch", fetcher); const view = show(true);
  await screen.findByText(/Шаблонів ще немає/); submit();
  expect(fetcher.mock.calls.filter(([request]) => request.method === "POST")).toHaveLength(0);
  view.rerender(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} /></I18nextProvider>);
  choose(file()); submit();
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  submit(); expect(fetcher.mock.calls.filter(([request]) => request.method === "POST")).toHaveLength(1);
  expect(screen.getByRole("tab", { name: "Документи" })).toBeDisabled();
  view.unmount(); await act(async () => finish(Response.json(item)));
  expect(onSaved).not.toHaveBeenCalled(); expect(onBusy).toHaveBeenLastCalledWith(false);
});

test("authenticated navigation and language saves preserve the upload draft and canonical routes", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (request.method === "PATCH") return Response.json({ ...session, user: { ...session.user, ui_language: "en" } });
    return defaults(request);
  }));
  render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>);
  await screen.findByRole("heading", { name: "Бібліотека документів" });
  expect(window.location.pathname).toBe("/documents");
  choose(file());
  fireEvent.change(screen.getByLabelText("Назва документа"), { target: { value: "Незбережена заява" } });
  const before = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(before); expect(before.defaultPrevented).toBe(true);
  fireEvent.click(screen.getByRole("link", { name: "Профіль" }));
  expect(window.location.pathname).toBe("/profile");
  fireEvent.change(screen.getByRole("combobox", { name: "Мова інтерфейсу" }), { target: { value: "en" } });
  fireEvent.click(screen.getByRole("button", { name: "Зберегти мову" }));
  expect(await screen.findByText("Your language preference has been saved.")).toBeVisible();
  fireEvent.click(screen.getByRole("link", { name: "Document library" }));
  expect(screen.getByLabelText("Document title")).toHaveValue("Незбережена заява");
  expect((screen.getByLabelText("DOCX file") as HTMLInputElement).files?.[0].name).toBe("Заява Ґанни.docx");
  expect(document.documentElement.lang).toBe("en");
  act(() => { window.history.replaceState(null, "", "/profile"); window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(screen.getByRole("heading", { name: "Profile" })).toBeVisible();
});

test("a missing session never mounts private library/profile content", () => {
  vi.stubGlobal("fetch", vi.fn());
  const view = render(<SessionPages session={{ user: null, csrf_token: "x" }} accept={vi.fn()} authBusy={false} setAuthBusy={vi.fn()} />);
  expect(view.container).toBeEmptyDOMElement();
  expect(fetch).not.toHaveBeenCalled();
});

test("an in-flight upload prevents logout/navigation and refreshes profile usage on success", async () => {
  let finish!: (response: Response) => void;
  let quotaReads = 0;
  vi.stubGlobal("fetch", vi.fn((request: Request) => {
    if (request.method === "POST") return new Promise<Response>(resolve => { finish = resolve; });
    if (typeof request !== "string" && new URL(request.url).pathname === "/api/storage/usage") quotaReads++;
    return Promise.resolve(defaults(request));
  }));
  render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>);
  await screen.findByText(/Шаблонів ще немає/);
  choose(file()); submit();
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  expect(screen.getByRole("button", { name: "Вийти" })).toBeDisabled();
  fireEvent.click(screen.getByRole("link", { name: "Профіль" }));
  expect(window.location.pathname).toBe("/documents");
  await act(async () => finish(Response.json(item)));
  await waitFor(() => expect(quotaReads).toBeGreaterThanOrEqual(4));
  expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled();
  const before = new Event("beforeunload", { cancelable: true }); window.dispatchEvent(before);
  expect(before.defaultPrevented).toBe(false);
});
