import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Profile } from "../src/accounts/Profile";
import { Authentication, type Session } from "../src/accounts/Authentication";
import { i18n, setLanguage } from "../src/i18n";

const user = { id: "owner", login: "owner@example.test", display_name: "Ґанна", role: "user", ui_language: "uk" } as const;
const session: Session = { user, csrf_token: "csrf" };
const usage = { limit_bytes: 1000, used_bytes: 8, reserved_bytes: 2, available_bytes: 990, over_limit: false };
const failure = (code: string) => Response.json({ error: { code, parameters: {} } }, { status: 400 });
const onSession = vi.fn();
const onBusy = vi.fn();
function show(disabled = false) {
  return render(<I18nextProvider i18n={i18n}><Profile user={user} csrfToken="csrf" onSession={onSession} onBusy={onBusy} disabled={disabled} /></I18nextProvider>);
}
function nameForm() { return screen.getByRole("form", { name: "Дані облікового запису" }); }
function passwordForm() { return screen.getByRole("form", { name: "Зміна пароля" }); }
function passwords(confirm = "New-password-їжак") {
  fireEvent.change(screen.getByLabelText("Поточний пароль"), { target: { value: "Old-password-їжак" } });
  fireEvent.change(screen.getByLabelText("Новий пароль"), { target: { value: "New-password-їжак" } });
  fireEvent.change(screen.getByLabelText("Підтвердьте новий пароль"), { target: { value: confirm } });
}
beforeEach(async () => { onSession.mockClear(); onBusy.mockClear(); await setLanguage("uk"); });

test("name save preserves failed drafts, sends only allowed data and accepts canonical success", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(usage))
    .mockResolvedValueOnce(failure("forbidden"))
    .mockResolvedValueOnce(Response.json({ ...session, user: { ...user, display_name: "Єва" } }));
  vi.stubGlobal("fetch", fetcher);
  show();
  expect(await screen.findByText("8 байтів")).toBeVisible();
  expect(screen.getByLabelText("Логін")).toHaveAttribute("readonly");
  fireEvent.change(screen.getByLabelText("Ім’я для відображення"), { target: { value: "  Єва  " } });
  fireEvent.submit(nameForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("Дія недоступна");
  expect(screen.getByLabelText("Ім’я для відображення")).toHaveValue("  Єва  ");
  expect(onSession).not.toHaveBeenCalled();
  fireEvent.submit(nameForm());
  expect(await screen.findByText("Ім’я для відображення збережено.")).toBeVisible();
  expect(screen.getByLabelText("Ім’я для відображення")).toHaveValue("Єва");
  const request = fetcher.mock.calls[2][0] as Request;
  expect(request.headers.get("X-CSRF-Token")).toBe("csrf");
  expect(await request.json()).toEqual({ display_name: "  Єва  " });
  expect(onSession).toHaveBeenCalledWith(expect.objectContaining({ csrf_token: "csrf" }));
});

test("password validation, failures and successful rotation preserve or clear the appropriate inputs", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(usage))
    .mockResolvedValueOnce(failure("current_password_invalid"))
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(Response.json({ ...session, csrf_token: "rotated" }));
  vi.stubGlobal("fetch", fetcher);
  show();
  await screen.findByText("8 байтів");
  passwords("Different-password");
  fireEvent.submit(passwordForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("не збігаються");
  expect(fetcher).toHaveBeenCalledTimes(1);
  passwords();
  fireEvent.submit(passwordForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("Поточний пароль неправильний");
  fireEvent.submit(passwordForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("Сталася помилка");
  expect(screen.getByLabelText("Новий пароль")).toHaveValue("New-password-їжак");
  fireEvent.submit(passwordForm());
  expect(await screen.findByText("Пароль змінено. Інші сеанси завершено.")).toBeVisible();
  expect(screen.getByLabelText("Поточний пароль")).toHaveValue("");
  expect(screen.getByLabelText("Новий пароль")).toHaveValue("");
  expect(screen.getByLabelText("Підтвердьте новий пароль")).toHaveValue("");
  expect(await (fetcher.mock.calls[3][0] as Request).json()).toEqual({ current_password: "Old-password-їжак", new_password: "New-password-їжак" });
  expect(onSession).toHaveBeenCalledWith(expect.objectContaining({ csrf_token: "rotated" }));
});

test("a short new password shows the localized inline minimum without a request", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json(usage));
  vi.stubGlobal("fetch", fetcher);
  show();
  await screen.findByText("8 байтів");
  fireEvent.change(screen.getByLabelText("Поточний пароль"), { target: { value: "Old-password-їжак" } });
  fireEvent.change(screen.getByLabelText("Новий пароль"), { target: { value: "короткий" } });
  fireEvent.change(screen.getByLabelText("Підтвердьте новий пароль"), { target: { value: "короткий" } });
  fireEvent.submit(passwordForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("щонайменше 10 символів");
  expect(fetcher).toHaveBeenCalledTimes(1);
  await act(() => setLanguage("en"));
  fireEvent.change(screen.getByLabelText("New password"), { target: { value: "short-9ch" } });
  fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "short-9ch" } });
  fireEvent.submit(screen.getByRole("form", { name: "Change password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("at least 10 characters");
  expect(fetcher).toHaveBeenCalledTimes(1);
});

test("a 422 invalid_request names the offending field in both locales", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ error: { code: "invalid_request", parameters: {} } }))
    .mockResolvedValueOnce(Response.json(usage))
    .mockResolvedValueOnce(Response.json(
      { error: { code: "invalid_request", parameters: { parameter: "display_name", reason: "extra_forbidden" } } },
      { status: 422 },
    ))
    .mockResolvedValueOnce(Response.json(
      { error: { code: "invalid_request", parameters: {} } },
      { status: 422 },
    ));
  vi.stubGlobal("fetch", fetcher);
  show();
  await screen.findByText("8 байтів");
  fireEvent.change(screen.getByLabelText("Ім’я для відображення"), { target: { value: "Ґанна" } });
  fireEvent.submit(nameForm());
  expect(await screen.findByRole("alert")).toHaveTextContent("Перевірте значення поля display_name.");
  await act(() => setLanguage("en"));
  expect(screen.getByRole("alert")).toHaveTextContent("Check the display_name field.");
  fireEvent.submit(screen.getByRole("form", { name: "Account details" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Check the entered information.");
  await act(() => setLanguage("uk"));
  expect(screen.getByRole("alert")).toHaveTextContent("Перевірте введені дані.");
});

test("usage failures retry without discarding drafts and copy updates with locale", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(failure("dependencies_unavailable"))
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(Response.json({ ...usage, limit_bytes: 0, available_bytes: 0, over_limit: true })));
  show();
  fireEvent.change(screen.getByLabelText("Ім’я для відображення"), { target: { value: "Чернетка" } });
  expect(await screen.findByRole("alert")).toHaveTextContent("Сервер тимчасово");
  fireEvent.click(screen.getByRole("button", { name: "Оновити використання" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Сталася помилка");
  fireEvent.click(screen.getByRole("button", { name: "Оновити використання" }));
  expect(await screen.findByText(/Використання перевищує/)).toBeVisible();
  await act(() => setLanguage("en"));
  expect(screen.getByLabelText("Display name")).toHaveValue("Чернетка");
  expect(screen.getByText("8 bytes")).toBeVisible();
  expect(screen.getByText(/Your usage exceeds/)).toBeVisible();
});

test("busy and parent-disabled forms prevent duplicate work; an unmounted response cannot restore a session", async () => {
  let complete!: (response: Response) => void;
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(usage))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { complete = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  const view = show(true);
  await screen.findByText("8 байтів");
  fireEvent.submit(nameForm());
  expect(fetcher).toHaveBeenCalledTimes(1);
  view.rerender(<I18nextProvider i18n={i18n}><Profile user={user} csrfToken="csrf" onSession={onSession} onBusy={onBusy} disabled={false} /></I18nextProvider>);
  fireEvent.submit(nameForm());
  fireEvent.submit(nameForm());
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("button", { name: "Зберегти ім’я" })).toBeDisabled();
  view.unmount();
  await act(async () => complete(Response.json(session)));
  expect(onSession).not.toHaveBeenCalled();
  expect(onBusy).toHaveBeenLastCalledWith(false);
});

test("unmount cancels pending usage and request failures without late UI updates", async () => {
  let fail!: (error: Error) => void;
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise((_resolve, reject) => { fail = reject; })));
  const view = show();
  view.unmount();
  await act(async () => fail(new Error("aborted")));
  expect(onSession).not.toHaveBeenCalled();
});

test("profile and authentication serialize saves with logout", async () => {
  let complete!: (response: Response) => void;
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(session))
    .mockResolvedValueOnce(Response.json(usage))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { complete = resolve; }))
    .mockResolvedValueOnce(Response.json({ user: null, csrf_token: "anonymous" }));
  vi.stubGlobal("fetch", fetcher);
  render(<I18nextProvider i18n={i18n}><Authentication>{(state, actions) => state.user && <Profile user={state.user} csrfToken={state.csrf_token} onSession={actions.accept} onBusy={actions.setBusy} disabled={actions.busy} />}</Authentication></I18nextProvider>);
  await screen.findByText("8 байтів");
  fireEvent.submit(nameForm());
  expect(screen.getByRole("button", { name: "Вийти" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Вийти" }));
  expect(fetcher).toHaveBeenCalledTimes(3);
  await act(async () => complete(Response.json(session)));
  await waitFor(() => expect(screen.getByRole("button", { name: "Вийти" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Вийти" }));
  expect(await screen.findByRole("button", { name: "Увійти" })).toBeEnabled();
});

test("language applies only after success, preserves drafts, and resets failed choices", async () => {
  let finish!: (response: Response) => void;
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(session))
    .mockResolvedValueOnce(Response.json(usage))
    .mockResolvedValueOnce(failure("forbidden"))
    .mockRejectedValueOnce(new Error("offline"))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; }));
  vi.stubGlobal("fetch", fetcher);
  render(<I18nextProvider i18n={i18n}><Authentication>{(value, actions) => value.user && <Profile
    user={value.user} csrfToken={value.csrf_token} onSession={actions.accept} onBusy={actions.setBusy} disabled={actions.busy}
  />}</Authentication></I18nextProvider>);
  await screen.findByText("8 байтів");
  fireEvent.change(screen.getByLabelText("Ім’я для відображення"), { target: { value: "Чернетка Ґанни" } });
  passwords();
  const selector = screen.getByRole("combobox", { name: "Мова інтерфейсу" });
  for (const message of ["Дія недоступна", "Сталася помилка"]) {
    fireEvent.change(selector, { target: { value: "en" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти мову" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(selector).toHaveValue("uk");
    expect(i18n.language).toBe("uk");
  }
  fireEvent.change(selector, { target: { value: "en" } });
  fireEvent.click(screen.getByRole("button", { name: "Зберегти мову" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(5));
  expect(selector).toBeDisabled();
  expect(screen.getByRole("button", { name: "Вийти" })).toBeDisabled();
  expect(i18n.language).toBe("uk");
  await act(async () => finish(Response.json({ ...session, user: { ...user, ui_language: "en" } })));
  expect(await screen.findByText("Your language preference has been saved.")).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Interface language" })).toBe(selector);
  expect(selector).toHaveValue("en");
  expect(screen.getByLabelText("Display name")).toHaveValue("Чернетка Ґанни");
  expect(screen.getByLabelText("Current password")).toHaveValue("Old-password-їжак");
  expect(screen.getByLabelText("New password")).toHaveValue("New-password-їжак");
  expect(screen.getByLabelText("Confirm new password")).toHaveValue("New-password-їжак");
  const request = fetcher.mock.calls[4][0] as Request;
  expect(request.headers.get("X-CSRF-Token")).toBe("csrf");
  expect(await request.json()).toEqual({ ui_language: "en" });
  fireEvent.change(selector, { target: { value: "uk" } });
  expect(i18n.language).toBe("en");
});
