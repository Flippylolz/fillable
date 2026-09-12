import { File as NodeFile, Buffer } from "node:buffer";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Library } from "../src/library/Library";
import { App } from "../src/App";
import { SessionPages } from "../src/SessionPages";
import { i18n, setLanguage } from "../src/i18n";
import type { Kind } from "../src/library/useLibrary";

const usage = { used_bytes: 10, reserved_bytes: 2, limit_bytes: 1000, available_bytes: 988, over_limit: false };
const item = { id: "resource", kind: "template", title: "Ґанна <script>", original_filename: "Заява.docx", current_version_id: "version", size_bytes: 10, digest: "a".repeat(64), unsupported_count: 1, processing_status: "not_started", created_at: "2026-09-06T10:00:00Z", updated_at: "2026-09-06T10:00:00Z" };
const session = { csrf_token: "csrf", user: { id: "owner", login: "owner@example.test", display_name: "Ґанна", role: "user", ui_language: "uk" } };
const fail = (code: string) => Response.json({ error: { code, parameters: {} } }, { status: code === "rate_limited" ? 429 : 409 });
const onBusy = vi.fn(); const onDirty = vi.fn(); const onSaved = vi.fn(); const onTabChange = vi.fn();
const empty = () => Response.json({ items: [], next_cursor: null });
function show(disabled = false) { return render(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={disabled} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} onTabChange={onTabChange} /></I18nextProvider>); }
function file(name = "Заява Ґанни.docx", bytes: BlobPart[] = ["Original Ukrainian bytes: Їжак"]) { return new NodeFile(bytes as ConstructorParameters<typeof NodeFile>[0], name) as unknown as File; }
function choose(value: File) { fireEvent.change(screen.getByLabelText("Файл DOCX"), { target: { files: [value] } }); }
function openUpload() { fireEvent.click(screen.getByRole("button", { name: "Завантажити DOCX" })); }
function submit() { fireEvent.submit(screen.getByRole("form", { name: "Завантажити файл DOCX" })); }
function defaults(request: Request) {
  const path = new URL(typeof request === "string" ? request : request.url, window.location.origin).pathname;
  if (path.endsWith("/processing")) return Response.json({ source_version_id: "version", status: "not_started" });
  if (path === "/api/storage/usage") return Response.json(usage);
  if (path === "/api/auth/session") return Response.json(session);
  if (path === "/api/health") return Response.json({ status: "ok" });
  return empty();
}
beforeEach(async () => {
  // Match the accepted non-secure browser origin: randomUUID is unavailable.
  vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
  await setLanguage("uk"); window.history.replaceState(null, "", "/"); onBusy.mockClear(); onDirty.mockClear(); onSaved.mockClear(); onTabChange.mockClear();
});

test.each(["operation_aborted", "operation_conflict", "rate_limited"])("ambiguous upload retries preserve bytes and key; %s starts a new attempt", async code => {
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
  openUpload();
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
  expect(onTabChange).toHaveBeenCalledWith("document");
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
  vi.stubGlobal("fetch", fetcher); show(); await screen.findByText(/Шаблонів ще немає/); openUpload();
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

test("list errors retry, cursor failures keep saved rows, and pagination deduplicates", async () => {
  let lists = 0; let more = 0;
  const fetcher = vi.fn(async (request: Request) => {
    const url = new URL(request.url);
    if (url.searchParams.has("cursor")) {
      more++; if (more === 1) return fail("dependencies_unavailable");
      if (more === 2) throw new Error("offline");
      return Response.json({ items: [item, { ...item, id: "older", title: "Попередня" }], next_cursor: null });
    }
    lists++; if (lists === 1) return fail("dependencies_unavailable");
    return Response.json({ items: [item], next_cursor: "cursor" });
  });
  vi.stubGlobal("fetch", fetcher); show();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Оновити бібліотеку" }));
  expect(await screen.findByRole("article", { name: item.title })).toBeVisible();
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

test("a requested tab switches the gallery, ignores stale list results, and aborts on unmount", async () => {
  const finish: ((response: Response) => void)[] = [];
  const fetcher = vi.fn((request: Request) => {
    if (finish.length < 1) return new Promise<Response>(resolve => finish.push(resolve));
    return Promise.resolve(defaults(request));
  });
  vi.stubGlobal("fetch", fetcher);
  const library = (key: Kind) => <I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} onTabChange={onTabChange} tab={key} /></I18nextProvider>;
  const view = render(library("template"));
  await waitFor(() => expect(finish).toHaveLength(1));
  view.rerender(library("document"));
  expect(await screen.findByText(/Документів ще немає/)).toBeVisible();
  await act(async () => finish[0](Response.json({ items: [item] })));
  expect(screen.queryByRole("article")).toBeNull();
  view.rerender(library("template"));
  await screen.findByText(/Шаблонів ще немає/);
  view.rerender(library("document"));
  await screen.findByText(/Документів ще немає/);
  view.unmount();
  expect(fetcher.mock.calls.every(([request]) => request.signal.aborted)).toBe(true);
});

test("pending uploads block duplicate submits and late success cannot revive unmounted state", async () => {
  let finish!: (response: Response) => void;
  const fetcher = vi.fn((request: Request) => request.method === "POST" ? new Promise<Response>(resolve => { finish = resolve; }) : Promise.resolve(defaults(request)));
  vi.stubGlobal("fetch", fetcher); const view = show(true);
  await screen.findByText(/Шаблонів ще немає/);
  view.rerender(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} /></I18nextProvider>);
  openUpload();
  view.rerender(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={true} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} /></I18nextProvider>);
  submit();
  expect(fetcher.mock.calls.filter(([request]) => request.method === "POST")).toHaveLength(0);
  view.rerender(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} /></I18nextProvider>);
  choose(file()); submit();
  await waitFor(() => expect(finish).toBeTypeOf("function"));
  submit(); expect(fetcher.mock.calls.filter(([request]) => request.method === "POST")).toHaveLength(1);
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
  fireEvent.click(screen.getByRole("link", { name: "My documents" }));
  expect(screen.getByLabelText("Document title")).toHaveValue("Незбережена заява");
  expect((screen.getByLabelText("DOCX file") as HTMLInputElement).files?.[0].name).toBe("Заява Ґанни.docx");
  expect(document.documentElement.lang).toBe("en");
  act(() => { window.history.replaceState(null, "", "/profile"); window.dispatchEvent(new PopStateEvent("popstate")); });
  expect(screen.getByRole("heading", { name: "Profile" })).toBeVisible();
});

test("a missing session never mounts private library/profile content", () => {
  vi.stubGlobal("fetch", vi.fn());
  const view = render(<I18nextProvider i18n={i18n}><SessionPages session={{ user: null, csrf_token: "x" }} accept={vi.fn()} authBusy={false} setAuthBusy={vi.fn()} logout={vi.fn()} connection="ok" onRetry={vi.fn()} /></I18nextProvider>);
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
  openUpload();
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

test("pending deletion remains visible after loading and cannot offer a saved download", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/documents") return Response.json({ items: [{ ...item, deletion_pending: true }], next_cursor: null });
    return defaults(request);
  }));
  show();
  expect(await screen.findByRole("article", { name: item.title })).toBeVisible();
  expect(screen.getByRole("button", { name: "Повторити очищення" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Завантажити збережений DOCX" })).toBeNull();
  expect(screen.getByText(/Очищення ще не завершено/)).toBeVisible();
});

test("the card title link opens the resource; blocked and modified clicks do not", async () => {
  const onOpen = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/documents") return Response.json({ items: [item], next_cursor: null });
    return defaults(request);
  }));
  const view = render(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} onOpen={onOpen} /></I18nextProvider>);
  const card = await screen.findByRole("article", { name: item.title });
  const link = within(card).getByRole("link", { name: item.title });
  expect(link).toHaveAttribute("href", "/editor/resource");
  fireEvent.click(link);
  expect(onOpen).toHaveBeenNthCalledWith(1, "resource");
  fireEvent.click(link, { ctrlKey: true });
  expect(onOpen).toHaveBeenCalledTimes(1);
  view.rerender(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={true} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} onOpen={onOpen} /></I18nextProvider>);
  expect(screen.getByRole("link", { name: item.title })).toHaveAttribute("aria-disabled", "true");
  fireEvent.click(screen.getByRole("link", { name: item.title }));
  expect(onOpen).toHaveBeenCalledTimes(1);
});

test("pending deletion keeps the title as plain text and offers no open link", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/documents") return Response.json({ items: [{ ...item, deletion_pending: true }], next_cursor: null });
    return defaults(request);
  }));
  render(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} onOpen={vi.fn()} /></I18nextProvider>);
  expect(await screen.findByRole("article", { name: item.title })).toBeVisible();
  expect(screen.queryByRole("link", { name: item.title })).toBeNull();
  expect(screen.getByRole("heading", { name: item.title })).toHaveTextContent(item.title);
});

test("the upload toggle reveals the form and reports its expanded state", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  show();
  await screen.findByText(/Шаблонів ще немає/);
  const toggle = screen.getByRole("button", { name: "Завантажити DOCX" });
  const form = document.getElementById("library-upload")!;
  expect(form).toHaveAttribute("aria-labelledby", "upload-title");
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(toggle).toHaveAttribute("aria-controls", "library-upload");
  expect(form).not.toBeVisible();
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(form).toBeVisible();
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(form).not.toBeVisible();
});

test("search filters loaded cards by title and filename and reports an empty result", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/documents") return Response.json({ items: [item, { ...item, id: "other", title: "Довідка", original_filename: "help.docx" }], next_cursor: null });
    return defaults(request);
  }));
  show();
  await screen.findByRole("article", { name: item.title });
  const search = screen.getByRole("searchbox", { name: "Пошук документів…" });
  fireEvent.change(search, { target: { value: "ДОВІДКА" } });
  expect(screen.queryByRole("article", { name: item.title })).toBeNull();
  expect(screen.getByRole("article", { name: "Довідка" })).toBeVisible();
  fireEvent.change(search, { target: { value: "заява.docx" } });
  expect(screen.getByRole("article", { name: item.title })).toBeVisible();
  expect(screen.queryByRole("article", { name: "Довідка" })).toBeNull();
  fireEvent.change(search, { target: { value: "ніхто не шукав" } });
  expect(screen.getByText("Нічого не знайдено. Змініть запит пошуку.")).toBeVisible();
  fireEvent.change(search, { target: { value: "  " } });
  expect(screen.getAllByRole("article")).toHaveLength(2);
});

test("sorting reorders the visible gallery by date and title", async () => {
  const older = { ...item, id: "older", title: "Анна", updated_at: "2026-09-01T10:00:00Z" };
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/documents") return Response.json({ items: [item, older], next_cursor: null });
    return defaults(request);
  }));
  const { container } = show();
  await screen.findByRole("article", { name: item.title });
  const order = () => Array.from(container.querySelectorAll(".library-items article"), node => node.getAttribute("aria-label"));
  expect(order()).toEqual(["Ґанна <script>", "Анна"]);
  fireEvent.change(screen.getByRole("combobox", { name: "Сортування" }), { target: { value: "oldest" } });
  expect(order()).toEqual(["Анна", "Ґанна <script>"]);
  fireEvent.change(screen.getByRole("combobox", { name: "Сортування" }), { target: { value: "titleAsc" } });
  expect(order()).toEqual(["Анна", "Ґанна <script>"]);
  fireEvent.change(screen.getByRole("combobox", { name: "Сортування" }), { target: { value: "titleDesc" } });
  expect(order()).toEqual(["Ґанна <script>", "Анна"]);
});

test("an external tab request selects the matching gallery and reports changes", async () => {
  const onTabChange = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  const view = render(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} tab="document" onTabChange={onTabChange} /></I18nextProvider>);
  await screen.findByText(/Документів ще немає/);
  view.rerender(<I18nextProvider i18n={i18n}><Library csrfToken="csrf" disabled={false} onBusy={onBusy} onDirty={onDirty} onSaved={onSaved} tab="template" onTabChange={onTabChange} /></I18nextProvider>);
  await screen.findByText(/Шаблонів ще немає/);
  expect(onTabChange).not.toHaveBeenCalled();
});
