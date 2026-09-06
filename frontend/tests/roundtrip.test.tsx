import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { EditorState, TextSelection } from "prosemirror-state";
import { splitBlock } from "prosemirror-commands";
import { RoundtripProof } from "../src/editor/RoundtripProof";
import { paragraphIdentities } from "../src/editor/transactions";
import { editorSchema } from "../src/editor/model";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";

const initial = { source: "fixture", digest: "revision", model: corpus };
function show() {
  return render(
    <I18nextProvider i18n={i18n}>
      <RoundtripProof />
    </I18nextProvider>,
  );
}

test("export captures the editor draft, failure preserves it, reopen replaces the revision", async () => {
  await setLanguage("en");
  const fetcher = vi.fn().mockResolvedValueOnce(Response.json(initial));
  vi.stubGlobal("fetch", fetcher);
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:proof"),
    revokeObjectURL: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  show();
  const value = (
    await screen.findAllByRole("textbox", { name: "Field value: ПІБ клієнта" })
  )[0];
  fireEvent.change(value, { target: { value: "Ґанна Їжак" } });
  fetcher.mockResolvedValueOnce(new Response("failed", { status: 400 }));
  fireEvent.click(screen.getByRole("button", { name: "Export DOCX" }));
  await screen.findByRole("alert");
  expect(value).toHaveValue("Ґанна Їжак");
  expect(JSON.parse(fetcher.mock.calls[1][1].body).model).toEqual(
    expect.objectContaining({ type: "doc" }),
  );
  expect(fetcher.mock.calls[1][1].body).toContain("Ґанна Їжак");
  fetcher.mockResolvedValueOnce(new Response("exported"));
  fireEvent.click(screen.getByRole("button", { name: "Export DOCX" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Reopen exported DOCX" }),
    ).toBeEnabled(),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  fetcher.mockResolvedValueOnce(Response.json(initial));
  fireEvent.click(screen.getByRole("button", { name: "Reopen exported DOCX" }));
  await waitFor(() => expect(value.isConnected).toBe(false));
  expect(fetcher.mock.calls[3][1].body).toBeInstanceOf(Blob);
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 1050));
  });
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:proof");
});

test("load errors are visible and unmount aborts pending loading", async () => {
  await setLanguage("en");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("failed", { status: 500 })),
  );
  const first = show();
  await screen.findByRole("alert");
  first.unmount();
  let signal: AbortSignal;
  vi.stubGlobal(
    "fetch",
    vi.fn((_url, options) => {
      signal = options.signal;
      return new Promise((_resolve, reject) =>
        signal.addEventListener("abort", () => reject(new Error("aborted"))),
      );
    }),
  );
  const second = show();
  second.unmount();
  await act(async () => {});
  expect(signal!.aborted).toBe(true);
});

test("Enter allocates distinct paragraph identities and preserves the source style", () => {
  const paragraph = editorSchema.nodes.paragraph.create(
    { id: "word/document.xml:1", align: "right" },
    editorSchema.text("before after"),
  );
  let state = EditorState.create({
    doc: editorSchema.nodes.doc.create(
      null,
      editorSchema.nodes.section.create(
        { part: "word/document.xml" },
        paragraph,
      ),
    ),
  });
  state = state.apply(
    state.tr.setSelection(TextSelection.create(state.doc, 8)),
  );
  expect(paragraphIdentities(state.tr)).toBeInstanceOf(Object);
  splitBlock(state, (transaction) => {
    state = state.apply(paragraphIdentities(transaction));
  });
  const first = state.doc.firstChild!.child(0),
    second = state.doc.firstChild!.child(1);
  expect(second.attrs.id).toMatch(/^new:word\/document.xml:1:[a-f0-9]{32}$/);
  expect(second.attrs.id).not.toBe(first.attrs.id);
  expect(second.attrs.align).toBe("right");
});

test("removing one control keeps its value and undo restores its identity", async () => {
  await setLanguage("en");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(initial)));
  show();
  const buttons = await screen.findAllByRole("button", {
    name: "Remove field: ПІБ клієнта",
  });
  fireEvent.click(buttons[0]);
  expect(
    screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" }),
  ).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  expect(
    screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" }),
  ).toHaveLength(2);
});
