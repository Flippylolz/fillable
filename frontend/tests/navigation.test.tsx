import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { App } from "../src/App";
import { i18n, setLanguage } from "../src/i18n";

const session = { csrf_token: "csrf", user: { id: "owner", login: "owner@example.test", display_name: "Ґанна", role: "user", ui_language: "uk" } };
const usage = { used_bytes: 0, reserved_bytes: 0, limit_bytes: 1000, available_bytes: 1000, over_limit: false };
function defaults(request: Request) {
  const path = new URL(request.url, window.location.origin).pathname;
  if (path === "/api/storage/usage") return Response.json(usage);
  if (path === "/api/auth/session") return Response.json(session);
  if (path === "/api/health") return Response.json({ status: "ok" });
  return Response.json({ items: [], next_cursor: null });
}
beforeEach(async () => {
  // Match the accepted non-secure browser origin: randomUUID is unavailable.
  vi.stubGlobal("crypto", { getRandomValues: crypto.getRandomValues.bind(crypto) });
  await setLanguage("uk"); window.history.replaceState(null, "", "/documents");
});

test("the brand is a home link to the document library", async () => {
  vi.stubGlobal("fetch", vi.fn((request: Request) => Promise.resolve(defaults(request))));
  render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>);
  const home = await screen.findByRole("link", { name: "Fillable — на головну" });
  expect(home).toHaveAttribute("href", "/documents");
  expect(home).toHaveTextContent("Fillable");
});

test("navigation separates content tabs from the account link and marks the current page", async () => {
  vi.stubGlobal("fetch", vi.fn((request: Request) => Promise.resolve(defaults(request))));
  render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>);
  await screen.findByText(/Шаблонів ще немає/);
  const documents = screen.getByRole("link", { name: "Бібліотека документів" });
  const profile = screen.getByRole("link", { name: "Профіль" });
  expect(documents).toHaveAttribute("aria-current", "page");
  expect(profile).not.toHaveAttribute("aria-current");
  expect(profile).toHaveClass("page-nav-account");
  fireEvent.click(profile);
  await screen.findByRole("heading", { name: "Профіль" });
  expect(window.location.pathname).toBe("/profile");
  expect(profile).toHaveAttribute("aria-current", "page");
  expect(documents).not.toHaveAttribute("aria-current", "page");
  // The signed-in strip keeps identity and logout only; session recovery is automatic.
  expect(screen.queryByRole("button", { name: "Увійти знову" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled();
});
