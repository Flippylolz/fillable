import { StrictMode } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Reauthentication } from "../src/accounts/Reauthentication";
import { i18n, setLanguage } from "../src/i18n";
import type { Session } from "../src/accounts/Authentication";

const owner: NonNullable<Session["user"]> = { id: "owner", login: "owner@example.test", display_name: "Ґанна", role: "user", ui_language: "en" };
const anonymous: Session = { user: null, csrf_token: "fresh-anonymous" };
const restored: Session = { user: owner, csrf_token: "new-authenticated" };
const other: Session = { user: { ...owner, id: "other", login: "other@example.test" }, csrf_token: "other-csrf" };
const failure = (code = "internal_error", status = 503) => Response.json({ error: { code } }, { status });
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
function show() {
  const recovered = vi.fn(), guard = vi.fn(() => true);
  const view = render(<I18nextProvider i18n={i18n}><Reauthentication owner={owner} onRecovered={recovered} allowDiscard={guard} /></I18nextProvider>);
  return { ...view, recovered, guard };
}
beforeEach(async () => setLanguage("en"));

test("same-owner bootstrap recovers once under strict effect replay without asking for credentials", async () => {
  const recovered = vi.fn(); vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(Response.json(restored))));
  render(<StrictMode><I18nextProvider i18n={i18n}><Reauthentication owner={owner} onRecovered={recovered} allowDiscard={() => true} /></I18nextProvider></StrictMode>);
  await waitFor(() => expect(recovered).toHaveBeenCalledTimes(1)); expect(recovered).toHaveBeenCalledWith(restored);
});

test("fresh CSRF and the fixed owner are used for login; failed credentials preserve the password and success clears it", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(anonymous)).mockResolvedValueOnce(failure("invalid_credentials", 401)).mockResolvedValueOnce(Response.json(restored));
  vi.stubGlobal("fetch", fetcher); const state = show();
  const password = await screen.findByLabelText("Password");
  expect(screen.getByLabelText("Login")).toHaveAttribute("readonly");
  fireEvent.change(password, { target: { value: "Synthetic-Їжак-2026" } }); submit();
  await screen.findByText("The login or password is incorrect."); expect(password).toHaveValue("Synthetic-Їжак-2026");
  const sent = fetcher.mock.calls[1][0] as Request;
  expect(sent.headers.get("X-CSRF-Token")).toBe(anonymous.csrf_token);
  expect(await sent.clone().json()).toEqual({ login: owner.login, password: "Synthetic-Їжак-2026" });
  submit(); await waitFor(() => expect(state.recovered).toHaveBeenCalledWith(restored)); expect(password).toHaveValue("");
});

test.each(["authentication_required", "forbidden"])("expired recovery credentials (%s) offer fresh bootstrap", async code => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(anonymous)).mockResolvedValueOnce(failure(code, code === "forbidden" ? 403 : 401)).mockResolvedValueOnce(Response.json(restored));
  vi.stubGlobal("fetch", fetcher); const state = show();
  fireEvent.change(await screen.findByLabelText("Password"), { target: { value: "password" } }); submit();
  fireEvent.click(await screen.findByRole("button", { name: "Retry loading" }));
  await waitFor(() => expect(state.recovered).toHaveBeenCalledWith(restored));
});

test.each(["anonymous", "different"])("switching from %s recovery requires the discard guard", async kind => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(kind === "anonymous" ? anonymous : other)));
  const state = show(); state.guard.mockReturnValueOnce(false);
  const button = await screen.findByRole("button", { name: kind === "anonymous" ? "Leave this workspace and use another account" : "Switch to other@example.test" });
  fireEvent.click(button); expect(state.recovered).not.toHaveBeenCalled();
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("region", { name: "Відновлення сесії" })).toBeVisible();
  fireEvent.click(button); expect(state.recovered).toHaveBeenCalledWith(kind === "anonymous" ? anonymous : other);
});

test("a login result for a different owner never silently adopts that account", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json(anonymous)).mockResolvedValueOnce(Response.json(other)));
  const state = show(); fireEvent.change(await screen.findByLabelText("Password"), { target: { value: "password" } }); submit();
  await screen.findByRole("button", { name: "Switch to other@example.test" });
  expect(state.recovered).not.toHaveBeenCalled(); expect(screen.getByRole("alert")).toHaveTextContent("Another account is active");
});

test.each(["response", "network"])("bootstrap %s failure has a retry", async mode => {
  const fetcher = vi.fn();
  if (mode === "network") fetcher.mockRejectedValueOnce(new Error("offline")); else fetcher.mockResolvedValueOnce(failure());
  fetcher.mockResolvedValueOnce(Response.json(anonymous)); vi.stubGlobal("fetch", fetcher); show();
  fireEvent.click(await screen.findByRole("button", { name: "Retry loading" }));
  await screen.findByLabelText("Password");
});

test.each(["response", "network"])("unmount aborts and ignores a late bootstrap %s", async mode => {
  let complete!: (value: Response) => void, fail!: (error: Error) => void;
  const fetcher = vi.fn(() => new Promise<Response>((resolve, reject) => { complete = resolve; fail = reject; }));
  vi.stubGlobal("fetch", fetcher); const state = show(); state.unmount();
  expect((fetcher.mock.calls[0] as unknown as [Request])[0].signal.aborted).toBe(true);
  await act(async () => { if (mode === "response") complete(Response.json(restored)); else fail(new Error("offline")); });
  expect(state.recovered).not.toHaveBeenCalled();
});

test("a pending login prevents duplicate submissions and late unmounted results cannot recover", async () => {
  let complete!: (value: Response) => void;
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(anonymous)).mockImplementationOnce(() => new Promise<Response>(resolve => { complete = resolve; }));
  vi.stubGlobal("fetch", fetcher); const state = show();
  fireEvent.change(await screen.findByLabelText("Password"), { target: { value: "password" } }); submit();
  await waitFor(() => expect(screen.getByRole("button", { name: "Sign in again" })).toBeDisabled());
  fireEvent.submit(screen.getByRole("button", { name: "Sign in again" }).closest("form")!);
  expect(fetcher).toHaveBeenCalledTimes(2); state.unmount();
  expect(fetcher.mock.calls[1][0].signal.aborted).toBe(true);
  await act(async () => complete(Response.json(restored))); expect(state.recovered).not.toHaveBeenCalled();
});

test("login network failure keeps credentials available for retry", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json(anonymous)).mockRejectedValueOnce(new Error("offline")));
  show(); const password = await screen.findByLabelText("Password"); fireEvent.change(password, { target: { value: "retained" } }); submit();
  await within(screen.getByRole("region", { name: "Restore your session" })).findByRole("alert");
  expect(password).toHaveValue("retained"); expect(screen.getByRole("button", { name: "Sign in again" })).toBeEnabled();
});

test.each(["bootstrap", "login"])("%s timeout aborts its request and offers recovery without losing the owner", async stage => {
  vi.useFakeTimers();
  try {
    const fetcher = vi.fn();
    if (stage === "login") fetcher.mockResolvedValueOnce(Response.json(anonymous));
    fetcher.mockImplementation((request: Request) => new Promise((_resolve, reject) => request.signal.addEventListener("abort", () => reject(new Error("timeout")))));
    vi.stubGlobal("fetch", fetcher); const state = show();
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    if (stage === "login") { fireEvent.change(screen.getByLabelText("Password"), { target: { value: "retained" } }); submit(); }
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(fetcher.mock.calls.at(-1)![0].signal.aborted).toBe(true);
    expect(screen.getByRole("alert")).toBeVisible(); expect(state.recovered).not.toHaveBeenCalled();
    if (stage === "bootstrap") expect(screen.getByRole("button", { name: "Retry loading" })).toBeEnabled();
    else { expect(screen.getByLabelText("Password")).toHaveValue("retained"); expect(screen.getByLabelText("Login")).toHaveValue(owner.login); }
  } finally { vi.useRealTimers(); }
});
