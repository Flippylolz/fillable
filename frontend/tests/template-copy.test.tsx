import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { UseTemplate } from "../src/library/UseTemplate";
import type { Resource } from "../src/library/useLibrary";
import { i18n, setLanguage } from "../src/i18n";

const item = { id: "source", current_version_id: "v1", title: "Шаблон Їжака" } as Resource;
const target = { ...item, id: "independent", kind: "document" };
const onBusy = vi.fn(); const onCreated = vi.fn();
function ui(disabled = false) { return <I18nextProvider i18n={i18n}><UseTemplate item={item} csrfToken="csrf" disabled={disabled} onBusy={onBusy} onCreated={onCreated} /></I18nextProvider>; }
function submit() { fireEvent.submit(screen.getByRole("form")); }
beforeEach(async () => { await setLanguage("uk"); onBusy.mockClear(); onCreated.mockClear(); });

test.each(["operation_aborted", "operation_conflict", "rate_limited", "quota_exceeded"])("copy preserves title and ambiguous retry key, then rotates on %s", async code => {
  const fetcher = vi.fn().mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(Response.json({ error: { code } }, { status: 409 }))
    .mockResolvedValueOnce(Response.json(target));
  vi.stubGlobal("fetch", fetcher); render(ui()); fireEvent.click(screen.getByRole("button"));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Незалежна заява" } });
  submit(); await screen.findByRole("alert");
  expect(screen.getByRole("textbox")).toHaveValue("Незалежна заява"); expect(onCreated).not.toHaveBeenCalled();
  await act(() => setLanguage("en")); expect(screen.getByRole("textbox")).toHaveValue("Незалежна заява");
  submit(); await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(screen.getByRole("button", { name: "Create and open document" })).toBeEnabled());
  submit(); await waitFor(() => expect(onCreated).toHaveBeenCalledWith(target));
  const requests = fetcher.mock.calls.map(([request]) => request as Request);
  expect(requests[0].headers.get("idempotency-key")).toBe(requests[1].headers.get("idempotency-key"));
  expect(requests[2].headers.get("idempotency-key")).not.toBe(requests[1].headers.get("idempotency-key"));
  expect(requests[0].headers.get("X-CSRF-Token")).toBe("csrf");
  expect(await requests[0].json()).toEqual({ title: "Незалежна заява", source_version_id: "v1" });
  expect(onBusy).toHaveBeenLastCalledWith(false); expect(screen.queryByRole("form")).toBeNull();
});

test.each([false, true])("pending copy blocks duplicates; unmount ignores late outcome (%s)", async reject => {
  let finish!: (response: Response) => void; let fail!: (error: Error) => void;
  const fetcher = vi.fn((_request: Request) => new Promise<Response>((resolve, rejection) => { finish = resolve; fail = rejection; }));
  vi.stubGlobal("fetch", fetcher); const view = render(ui(true));
  expect(screen.getByRole("button")).toBeDisabled(); view.rerender(ui());
  fireEvent.click(screen.getByRole("button")); submit();
  await waitFor(() => expect(screen.getByRole("textbox")).toBeDisabled()); submit();
  expect(fetcher).toHaveBeenCalledTimes(1); view.unmount();
  expect(fetcher.mock.calls[0][0].signal.aborted).toBe(true);
  await act(async () => { if (reject) fail(new Error("late")); else finish(Response.json(target)); });
  expect(onCreated).not.toHaveBeenCalled();
});

test("cancel and validation preserve title, and definitive edits change the retry identity", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ error: { code: "quota_exceeded" } }, { status: 409 }));
  vi.stubGlobal("fetch", fetcher); const view = render(ui()); fireEvent.click(screen.getByRole("button"));
  fireEvent.click(screen.getByRole("button", { name: "Скасувати" })); expect(screen.queryByRole("form")).toBeNull();
  fireEvent.click(screen.getByRole("button"));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: " " } }); submit();
  expect(fetcher).not.toHaveBeenCalled(); expect(screen.getByRole("alert")).toBeVisible();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "First" } });
  view.rerender(ui(true)); submit(); expect(fetcher).not.toHaveBeenCalled(); view.rerender(ui());
  submit(); await screen.findByRole("alert");
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Second" } });
  fetcher.mockResolvedValueOnce(Response.json(target)); submit(); await waitFor(() => expect(onCreated).toHaveBeenCalled());
  expect(fetcher.mock.calls[0][0].headers.get("idempotency-key")).not.toBe(fetcher.mock.calls[1][0].headers.get("idempotency-key"));
});
