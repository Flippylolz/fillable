import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { SessionPages } from "../src/SessionPages";
import { i18n, setLanguage } from "../src/i18n";

const user = { id: "owner", login: "owner@example.test", display_name: "Ґанна", role: "user" as const, ui_language: "uk" as const };
const session = { csrf_token: "csrf", user };
const usage = { used_bytes: 10, reserved_bytes: 2, limit_bytes: 1000, available_bytes: 988, over_limit: false };
const overLimit = { ...usage, used_bytes: 1200, reserved_bytes: 0, limit_bytes: 1000, available_bytes: 0, over_limit: true };
const base = { session, accept: vi.fn(), authBusy: false, setAuthBusy: vi.fn(), logout: vi.fn(), connection: "ok" as "loading" | "ok" | "error", onRetry: vi.fn() };

function defaults(request: Request) {
  const path = new URL(typeof request === "string" ? request : request.url, window.location.origin).pathname;
  if (path === "/api/storage/usage") return Response.json(usage);
  if (path === "/api/documents") return Response.json({ items: [], next_cursor: null });
  return Response.json({ status: "ok" });
}
function show(overrides: Partial<typeof base> = {}) {
  const props = { ...base, ...overrides };
  return render(<I18nextProvider i18n={i18n}><SessionPages {...props} /></I18nextProvider>);
}
beforeEach(async () => {
  vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
  await setLanguage("uk"); window.history.replaceState(null, "", "/documents");
  base.accept.mockClear(); base.setAuthBusy.mockClear(); base.logout.mockClear(); base.onRetry.mockClear();
});

test("the sidebar brands the application and marks the active section", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  show();
  await screen.findByText(/Шаблонів ще немає/);
  const brand = screen.getByRole("link", { name: "Fillable — на головну" });
  expect(brand).toHaveAttribute("href", "/documents");
  expect(screen.getByRole("link", { name: "Шаблони" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Мої документи" })).not.toHaveAttribute("aria-current");
  expect(screen.getByRole("link", { name: "Профіль" })).not.toHaveAttribute("aria-current");
});

test("sidebar section links preselect the matching library tab", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  show();
  await screen.findByText(/Шаблонів ще немає/);
  fireEvent.click(screen.getByRole("link", { name: "Мої документи" }));
  await waitFor(() => expect(screen.getByRole("tab", { name: "Документи" })).toHaveAttribute("aria-selected", "true"));
  expect(screen.getByRole("link", { name: "Мої документи" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Шаблони" })).not.toHaveAttribute("aria-current");
  expect(window.location.pathname).toBe("/documents");
});

test("the sidebar storage block shows usage, over-limit status, and localized errors", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/storage/usage") return Response.json(usage);
    return defaults(request);
  }));
  show();
  const block = await screen.findByRole("region", { name: "Сховище" });
  await within(block).findByText(/Використано 10 байтів із/);
  expect(within(block).getByRole("meter", { name: "Сховище" })).toHaveAttribute("max", "1000");
});

test("an over-limit allowance keeps files available and reports the exhausted quota", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/storage/usage") return Response.json(overLimit);
    return defaults(request);
  }));
  show();
  const block = await screen.findByRole("region", { name: "Сховище" });
  await within(block).findByText(/Використання перевищує/);
});

test("storage failures surface a localized alert in the sidebar", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
    if (new URL(request.url).pathname === "/api/storage/usage") throw new Error("offline");
    return defaults(request);
  }));
  show();
  const block = await screen.findByRole("region", { name: "Сховище" });
  await within(block).findByText("Сталася помилка. Спробуйте ще раз.");
});

test("the sidebar session footer signs out through the injected action", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  const view = show();
  await screen.findByText(/Шаблонів ще немає/);
  expect(screen.getByText(/увійшли як Ґанна/)).toBeVisible();  fireEvent.click(screen.getByRole("button", { name: "Вийти" }));
  expect(base.logout).toHaveBeenCalledTimes(1);
  view.rerender(<I18nextProvider i18n={i18n}><SessionPages {...base} authBusy={true} /></I18nextProvider>);
  expect(screen.getByRole("button", { name: "Вийти" })).toBeDisabled();
});

test("the connection status and retry live in the shell footer", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  show({ connection: "error" });
  await screen.findByText("Не вдалося з’єднатися із сервером");
  fireEvent.click(screen.getByRole("button", { name: "Спробувати знову" }));
  expect(base.onRetry).toHaveBeenCalledTimes(1);
});

test("the narrow-screen drawer opens from the menu bar and closes on Escape", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  show();
  await screen.findByText(/Шаблонів ще немає/);
  const menu = screen.getByRole("button", { name: "Меню" });
  const sidebar = document.getElementById("app-sidebar")!;
  expect(menu).toHaveAttribute("aria-expanded", "false");
  expect(menu).toHaveAttribute("aria-controls", "app-sidebar");
  fireEvent.click(menu);
  expect(menu).toHaveAttribute("aria-expanded", "true");
  expect(sidebar).toHaveClass("app-sidebar-open");
  expect(screen.getByRole("link", { name: "Fillable — на головну" })).toHaveFocus();
  fireEvent.keyDown(window, { key: "Escape" });
  expect(menu).toHaveAttribute("aria-expanded", "false");
  expect(sidebar).not.toHaveClass("app-sidebar-open");
});

test("the drawer scrim closes the navigation", async () => {
  vi.stubGlobal("fetch", vi.fn(async (request: Request) => defaults(request)));
  show();
  await screen.findByText(/Шаблонів ще немає/);
  fireEvent.click(screen.getByRole("button", { name: "Меню" }));
  fireEvent.click(document.querySelector(".shell-scrim")!);
  expect(document.getElementById("app-sidebar")).not.toHaveClass("app-sidebar-open");
});
