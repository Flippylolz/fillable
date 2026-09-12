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
  await screen.findByText(/Шаблонів ще немає/);
  // The public header link hands over to the sidebar brand once signed in.
  const home = screen.getByRole("link", { name: "Fillable — на головну" });
  expect(home).toHaveAttribute("href", "/documents");
  expect(home).toHaveTextContent("Fillable");
});

test("the sidebar marks the active section and hosts identity and sign-out", async () => {
  vi.stubGlobal("fetch", vi.fn((request: Request) => Promise.resolve(defaults(request))));
  render(<I18nextProvider i18n={i18n}><App /></I18nextProvider>);
  await screen.findByText(/Шаблонів ще немає/);
  const templates = screen.getByRole("link", { name: "Шаблони" });
  const documents = screen.getByRole("link", { name: "Мої документи" });
  const profile = screen.getByRole("link", { name: "Профіль" });
  expect(templates).toHaveAttribute("aria-current", "page");
  expect(documents).not.toHaveAttribute("aria-current");
  expect(profile).not.toHaveAttribute("aria-current");
  fireEvent.click(profile);
  await screen.findByRole("heading", { name: "Профіль" });
  expect(window.location.pathname).toBe("/profile");
  expect(profile).toHaveAttribute("aria-current", "page");
  expect(templates).not.toHaveAttribute("aria-current");
  fireEvent.click(documents);
  await screen.findByText(/Документів ще немає/);
  expect(window.location.pathname).toBe("/documents");
  expect(documents).toHaveAttribute("aria-current", "page");
  expect(templates).not.toHaveAttribute("aria-current");
  // The sidebar footer keeps identity and logout; session recovery is automatic.
  expect(screen.getByText(/увійшли як Ґанна/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Увійти знову" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled();
});
