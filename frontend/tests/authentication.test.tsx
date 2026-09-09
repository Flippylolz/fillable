import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Authentication } from "../src/accounts/Authentication";
import { i18n, setLanguage } from "../src/i18n";

const anonymous = { user: null, csrf_token: "anonymous-csrf" };
const signedIn = {
  user: {
    id: "123",
    login: "client@example.test",
    display_name: "Ґанна Їжак",
    role: "user",
    ui_language: "en",
  },
  csrf_token: "rotated-csrf",
};
const failure = (code: string, status = 401) =>
  Response.json({ error: { code, parameters: {} } }, { status });
const show = () =>
  render(
    <I18nextProvider i18n={i18n}>
      <Authentication>
        {(session) => <span data-testid="account">{session.user?.login}</span>}
      </Authentication>
    </I18nextProvider>,
  );
beforeEach(async () => {
  await setLanguage("uk");
});

async function credentials() {
  fireEvent.change(await screen.findByLabelText("Логін"), {
    target: { value: "client@example.test" },
  });
  fireEvent.change(screen.getByLabelText("Пароль"), {
    target: { value: "Synthetic-їжак-2026" },
  });
}

test("login sends CSRF, restores account language, preserves failed inputs, and logout rotates state", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json(anonymous))
    .mockResolvedValueOnce(failure("invalid_credentials"))
    .mockResolvedValueOnce(Response.json(signedIn))
    .mockResolvedValueOnce(failure("forbidden", 403))
    .mockResolvedValueOnce(Response.json(anonymous));
  vi.stubGlobal("fetch", fetcher);
  show();
  await credentials();
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Неправильний логін або пароль.");
  // The credentials alert renders inside the sign-in card, not at the page edge.
  expect(screen.getByRole("alert").closest("form")).not.toBeNull();
  expect(screen.getByLabelText("Пароль")).toHaveValue("Synthetic-їжак-2026");
  const request = fetcher.mock.calls[1][0] as Request;
  expect(request.headers.get("X-CSRF-Token")).toBe("anonymous-csrf");
  expect(await request.json()).toEqual({
    login: "client@example.test",
    password: "Synthetic-їжак-2026",
  });
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  expect(await screen.findByText("Signed in as Ґанна Їжак.")).toBeVisible();
  expect(screen.getByTestId("account")).toHaveTextContent(
    "client@example.test",
  );
  // Session recovery is automatic on expiry; the signed-in strip offers no manual trigger.
  expect(screen.queryByRole("button", { name: "Sign in again" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Увійти знову" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This action is unavailable",
  );
  expect(screen.getByTestId("account")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByLabelText("Password")).toHaveValue("");
  expect(fetcher.mock.calls[4][0].headers.get("X-CSRF-Token")).toBe(
    "rotated-csrf",
  );
  expect(screen.queryByTestId("account")).not.toBeInTheDocument();
});

test("session restoration takes the saved locale and network failures offer retry", async () => {
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(failure("authentication_required"))
    .mockResolvedValueOnce(Response.json(signedIn));
  vi.stubGlobal("fetch", fetcher);
  show();
  fireEvent.click(
    await screen.findByRole("button", { name: "Повторити завантаження" }),
  );
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("Увійдіть"),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Повторити завантаження" }),
  );
  expect(await screen.findByText("Signed in as Ґанна Їжак.")).toBeVisible();
  expect(i18n.language).toBe("en");
});

test("a rejected login request retains the form and prevents duplicate submission while pending", async () => {
  let reject!: (error: Error) => void;
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(Response.json(anonymous))
    .mockImplementationOnce(
      () =>
        new Promise((_resolve, fail) => {
          reject = fail;
        }),
    );
  vi.stubGlobal("fetch", fetcher);
  show();
  await credentials();
  const button = screen.getByRole("button", { name: "Увійти" });
  fireEvent.click(button);
  await waitFor(() => expect(button).toBeDisabled());
  fireEvent.submit(button.closest("form")!);
  expect(fetcher).toHaveBeenCalledTimes(2);
  await act(async () => reject(new Error("offline")));
  expect(screen.getByRole("alert")).toBeVisible();
  expect(screen.getByLabelText("Пароль")).toHaveValue("Synthetic-їжак-2026");
});

test("empty sign-in shows localized inline feedback without native bubbles or requests", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json(anonymous));
  vi.stubGlobal("fetch", fetcher);
  show();
  await screen.findByLabelText("Логін");
  expect(screen.getByLabelText("Логін")).not.toHaveAttribute("required");
  expect(screen.getByLabelText("Пароль")).not.toHaveAttribute("required");
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  expect(await screen.findByText("Введіть логін.")).toBeVisible();
  expect(screen.getByText("Введіть пароль.")).toBeVisible();
  expect(screen.getByLabelText("Логін")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByLabelText("Логін")).toHaveAccessibleDescription("Введіть логін.");
  expect(fetcher).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText("Логін"), { target: { value: "client@example.test" } });
  expect(screen.queryByText("Введіть логін.")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  expect(await screen.findByText("Введіть пароль.")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Пароль"), { target: { value: "Synthetic-їжак-2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  expect((fetcher.mock.calls[1][0] as Request).url).toContain("/api/auth/login");
  await act(async () => setLanguage("en"));
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Enter your password.")).toBeVisible();
});

test.each([true, false])(
  "unmount cancels session loading and ignores a late result (%s)",
  async (success) => {
    let complete!: (response: Response) => void;
    let fail!: (error: Error) => void;
    let request!: Request;
    vi.stubGlobal(
      "fetch",
      vi.fn((value) => {
        request = value;
        return new Promise((resolve, reject) => {
          complete = resolve;
          fail = reject;
        });
      }),
    );
    const view = show();
    view.unmount();
    expect(request.signal.aborted).toBe(true);
    await act(async () => {
      if (success) complete(Response.json(signedIn));
      else fail(new Error("aborted"));
    });
    expect(i18n.language).toBe("uk");
  },
);

test("protected expiry hides but retains the draft and resumes it with fresh same-owner credentials", async () => {
  const { api } = await import("../src/api");
  const fresh = { ...signedIn, csrf_token: "recovered-csrf" };
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(signedIn))
    .mockResolvedValueOnce(failure("authentication_required"))
    .mockResolvedValueOnce(Response.json(anonymous))
    .mockResolvedValueOnce(Response.json(fresh));
  vi.stubGlobal("fetch", fetcher);
  render(<I18nextProvider i18n={i18n}><Authentication>{(session, actions) =>
    <div><input aria-label="draft" defaultValue="Ґанна 🙂" /><span data-testid="csrf">{session.csrf_token}</span>
      <button disabled={actions.paused} onClick={() => void api.GET("/api/documents", { params: { query: { kind: "document" } } })}>Load documents</button></div>
  }</Authentication></I18nextProvider>);
  const draft = await screen.findByLabelText("draft");
  fireEvent.change(draft, { target: { value: "Unsaved Їжак" } });
  fireEvent.click(screen.getByRole("button", { name: "Load documents" }));
  const password = await screen.findByLabelText("Password");
  expect(draft).not.toBeVisible(); expect(draft).toHaveValue("Unsaved Їжак");
  expect(screen.getByText("Load documents")).toBeDisabled();
  fireEvent.change(password, { target: { value: "Synthetic-їжак-2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in again" }));
  await waitFor(() => expect(draft).toBeVisible());
  expect(screen.getByLabelText("draft")).toBe(draft);
  expect(draft).toHaveValue("Unsaved Їжак"); expect(screen.getByTestId("csrf")).toHaveTextContent("recovered-csrf");
});

test("expired-session recovery discards the old workspace only after its leave guard allows an account switch", async () => {
  const guard = vi.fn(() => false);
  const { api } = await import("../src/api");
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(signedIn))
    .mockResolvedValueOnce(failure("authentication_required"))
    .mockResolvedValueOnce(Response.json(anonymous));
  vi.stubGlobal("fetch", fetcher);
  render(<I18nextProvider i18n={i18n}><Authentication>{(_session, actions) =>
    <div><button onClick={() => actions.setLeaveGuard(guard)}>Protect draft</button>
      <button onClick={() => void api.GET("/api/documents", { params: { query: { kind: "document" } } })}>Load documents</button></div>
  }</Authentication></I18nextProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Protect draft" }));
  fireEvent.click(screen.getByRole("button", { name: "Load documents" }));
  const leave = await screen.findByRole("button", { name: "Leave this workspace and use another account" });
  fireEvent.click(leave); expect(guard).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Protect draft")).toBeInTheDocument();
  guard.mockReturnValue(true); fireEvent.click(leave);
  await screen.findByRole("button", { name: "Sign in" });
  expect(screen.queryByText("Protect draft")).not.toBeInTheDocument(); expect(window.location.pathname).toBe("/login");
});
