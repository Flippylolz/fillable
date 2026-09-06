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
    email: "client@example.test",
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
        {(session) => <span data-testid="account">{session.user?.email}</span>}
      </Authentication>
    </I18nextProvider>,
  );
beforeEach(async () => {
  await setLanguage("uk");
});

async function credentials() {
  fireEvent.change(await screen.findByLabelText("Електронна пошта"), {
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
  expect(await screen.findByRole("alert")).toHaveTextContent("Неправильна");
  expect(screen.getByLabelText("Пароль")).toHaveValue("Synthetic-їжак-2026");
  const request = fetcher.mock.calls[1][0] as Request;
  expect(request.headers.get("X-CSRF-Token")).toBe("anonymous-csrf");
  expect(await request.json()).toEqual({
    email: "client@example.test",
    password: "Synthetic-їжак-2026",
  });
  fireEvent.click(screen.getByRole("button", { name: "Увійти" }));
  expect(await screen.findByText("Signed in as Ґанна Їжак.")).toBeVisible();
  expect(screen.getByTestId("account")).toHaveTextContent(
    "client@example.test",
  );
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
