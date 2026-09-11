import { StrictMode, useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { DocumentEditor } from "../src/editor/DocumentEditor";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import { leaseResponse } from "./lease-response";

beforeEach(async () => {
  await setLanguage("en");
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

const initial = "[Введіть ПІБ клієнта]";

describe("fill mode layout", () => {
  function editorSetup(mode: "document" | "fill", readOnly = false) {
    const changed = vi.fn();
    render(<I18nextProvider i18n={i18n}>
      <DocumentEditor initialDocument={corpus} mode={mode} readOnly={readOnly} onDocumentChange={changed} />
    </I18nextProvider>);
    return { changed };
  }
  // CSS hiding is inert in jsdom, so queries are scoped to the fill form.
  const fillForm = () => within(document.querySelector(".fill-form") as HTMLElement);
  const entries = () => fillForm().getAllByRole("article");
  const firstValue = () => within(entries()[0]).getByRole("textbox");

  test("the working fields list in document order with typed inputs and markers", () => {
    editorSetup("fill");
    expect(screen.getByText("Fill in fields")).toBeVisible();
    expect(entries()).toHaveLength(5);
    expect(entries()[0]).toHaveAttribute("aria-label", "Field location 1: ПІБ клієнта");
    expect(entries()[0].querySelector(".field-type")!.textContent).toBe("Text");
    expect(within(entries()[0]).getByRole("textbox")).toHaveValue(initial);
    expect(within(entries()[0]).getByRole("button", { name: "Go to field: ПІБ клієнта" })).toBeEnabled();
  });

  test("fill edits propagate through the editor transactions with linked occurrences and undo", async () => {
    const { changed } = editorSetup("fill");
    const clients = entries().filter(entry => within(entry).getByRole("textbox").getAttribute("aria-label") === "Field value: ПІБ клієнта");
    expect(clients).toHaveLength(2);
    fireEvent.change(within(clients[0]).getByRole("textbox"), { target: { value: "Єва Ільїна" } });
    await waitFor(() => expect(changed).toHaveBeenCalled());
    await waitFor(() => expect(within(clients[1]).getByRole("textbox")).toHaveValue("Єва Ільїна"));
    const undo = fillForm().getByText("Undo", { exact: true });
    expect(undo).toBeEnabled();
    fireEvent.click(undo);
    await waitFor(() => expect(firstValue()).toHaveValue(initial));
    expect(fillForm().getByText("Redo", { exact: true })).toBeEnabled();
  });

  test("fill mode replaces the tools and sidebar with the form while the canvas stays mounted", () => {
    editorSetup("fill");
    expect(document.querySelector(".document-workbench")!.getAttribute("data-mode")).toBe("fill");
    expect(document.querySelector(".fill-layout")).not.toBeNull();
    expect(document.querySelector(".document-canvas")).not.toBeNull();
    expect(document.querySelector(".document-tools")).not.toBeNull();
    expect(document.querySelector("aside")).not.toBeNull();
  });

  test("the preview mirrors the document content after the bounded refresh", async () => {
    vi.useFakeTimers();
    editorSetup("fill");
    fireEvent.change(firstValue(), { target: { value: "Превʼю Ґанни" } });
    await act(async () => { vi.advanceTimersByTime(900); });
    const preview = document.querySelector(".fill-preview-content")!;
    expect(preview.querySelector(".ProseMirror")).not.toBeNull();
    expect(preview.textContent).toContain("Превʼю Ґанни");
    expect(preview.querySelector(".document-page-break")).toBeNull();
    vi.useRealTimers();
  });

  test("read-only fill mode disables the entries and undo", () => {
    editorSetup("fill", true);
    for (const entry of entries()) expect(within(entry).getByRole("textbox")).toBeDisabled();
    expect(fillForm().getByText("Undo", { exact: true })).toBeDisabled();
    expect(within(entries()[0]).getByRole("button", { name: "Remove field: ПІБ клієнта" })).toBeDisabled();
  });

  test("document mode keeps the canvas layout and the sidebar instead of the form", () => {
    editorSetup("document");
    expect(screen.getByRole("textbox", { name: "Editable document" })).toBeVisible();
    expect(document.querySelector(".document-workbench")!.getAttribute("data-mode")).toBe("document");
    expect(document.querySelector(".fill-form")).toBeNull();
    expect(within(document.querySelector("aside") as HTMLElement).getAllByRole("article")).toHaveLength(5);
  });

  test("an empty field list shows a localized empty state", () => {
    render(<I18nextProvider i18n={i18n}>
      <DocumentEditor initialDocument={{ type: "doc", content: [{ type: "paragraph" }] }} mode="fill" />
    </I18nextProvider>);
    expect(screen.getByText("No fields to fill. Switch to document mode to create fields or review suggestions.")).toBeVisible();
  });
});

describe("workspace view switch", () => {
  const id = "11111111-1111-4111-8111-111111111111";
  const v1 = "22222222-2222-4222-8222-222222222222";
  function workspaceSetup() {
    const server = { resource: { id, kind: "template", title: "Заява Їжака", original_filename: "Їжак.docx", current_version_id: v1,
      created_at: "2026-09-07", updated_at: "2026-09-07", size_bytes: 123, digest: "hash", unsupported_count: 0, deletion_pending: false, processing_status: "not_started" },
      document: structuredClone(corpus) as object, count: 1 };
    vi.stubGlobal("fetch", vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname;
      if (path.endsWith("/editing-lease")) return leaseResponse(request);
      if (path.endsWith("/content")) return Response.json(server);
      if (path.endsWith("/fields")) return Response.json({ source_version_id: server.resource.current_version_id, status: "not_started", snapshot: null });
      if (path.endsWith("/versions")) return Response.json({ error: { code: "internal_error", parameters: {} } }, { status: 500 });
      return Response.json(server.resource);
    }));
    function Host() {
      const [dirty, setDirty] = useState(false);
      return <StrictMode><Workspace identity={id} csrfToken="csrf" dirty={dirty} onDirty={setDirty} /></StrictMode>;
    }
    return render(<I18nextProvider i18n={i18n}><Host /></I18nextProvider>);
  }

  test("the toolbar switches between document and fill modes and disables while history is open", async () => {
    workspaceSetup();
    await screen.findByText("Editing enabled.");
    const workbench = document.querySelector(".document-workbench")!;
    expect(workbench.getAttribute("data-mode")).toBe("document");
    const fill = screen.getByRole("button", { name: "Fill" });
    expect(screen.getByRole("button", { name: "Document" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(fill);
    expect(fill).toHaveAttribute("aria-pressed", "true");
    expect(workbench.getAttribute("data-mode")).toBe("fill");
    expect(screen.getByText("Fill in fields")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Version history" }));
    expect(screen.getByRole("button", { name: "Fill" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Document" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Return to editing" }));
    expect(screen.getByRole("button", { name: "Fill" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Document" }));
    expect(workbench.getAttribute("data-mode")).toBe("document");
  });
});
