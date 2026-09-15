import { act, render, waitFor } from "@testing-library/react";
import { DocumentCover } from "../src/library/DocumentCover";
import { usePreviewReady } from "../src/workspace/usePreviewReady";
import type { Resource } from "../src/library/useLibrary";
import corpus from "../prototype/document.json";

const resource: Resource = { id: "11111111-1111-4111-8111-111111111111", current_version_id: "22222222-2222-4222-8222-222222222222", kind: "template", title: "Шаблон", original_filename: "test.docx", created_at: "2026-09-15", updated_at: "2026-09-15", size_bytes: 100, digest: "hash", unsupported_count: 0, deletion_pending: false, processing_status: "not_started", preview_ready: true };
const content = { resource, document: corpus, presentation: { section: { width: "595pt" } } };

beforeEach(() => {
  Object.defineProperty(Range.prototype, "getClientRects", { configurable: true, value: () => [] });
  Object.defineProperty(Range.prototype, "getBoundingClientRect", { configurable: true, value: () => new DOMRect() });
});

test("unrendered and deletion-pending resources show placeholders without fetching documents", () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<DocumentCover item={{ ...resource, preview_ready: false }} />);
  expect(document.querySelector(".library-preview-placeholder")).not.toBeNull();
  rerender(<DocumentCover item={{ ...resource, deletion_pending: true }} />);
  expect(fetch).not.toHaveBeenCalled();
});

test("a persisted preview draws the saved document and source layout and remains inert", async () => {
  const fetch = vi.fn(async (request: Request) => { expect(request.method).toBe("GET"); return Response.json(content); }); vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<DocumentCover item={resource} />);
  await waitFor(() => expect(document.querySelector(".library-preview-content")?.textContent).toContain("АНКЕТА КЛІЄНТА"));
  expect(document.querySelector(".library-preview")).toHaveAttribute("inert");
  expect(document.querySelector(".ProseMirror")).toHaveAttribute("contenteditable", "false");
  expect(document.querySelector("style")?.textContent).toContain("width:595pt");
  expect(document.querySelectorAll("table").length).toBeGreaterThan(0);
  expect(fetch.mock.calls[0][0].url).toContain(`source_version_id=${resource.current_version_id}`);
  rerender(<DocumentCover item={{ ...resource, current_version_id: "new-version", preview_ready: false }} />);
  expect(document.querySelector(".library-preview")).toBeNull();
  expect(document.querySelector(".library-preview-placeholder")).not.toBeNull();
});

test.each(["failure", "wrong-version", "network"])("%s leaves a placeholder", async scenario => {
  vi.stubGlobal("fetch", vi.fn(async () => {
    if (scenario === "network") throw new Error("offline");
    return scenario === "failure" ? Response.json({ error: { code: "not_found", parameters: {} } }, { status: 404 }) : Response.json({ ...content, resource: { ...resource, current_version_id: "other" } });
  }));
  await act(async () => { render(<DocumentCover item={resource} />); });
  expect(document.querySelector(".library-preview-placeholder")).not.toBeNull();
});

test("offscreen cards wait until visible and stale in-flight responses are discarded", async () => {
  let intersect: (entries: { isIntersecting: boolean }[]) => void = () => {};
  const disconnect = vi.fn();
  vi.stubGlobal("IntersectionObserver", class { constructor(callback: typeof intersect) { intersect = callback; } observe() {} disconnect = disconnect; });
  let resolve: (value: Response) => void = () => {};
  const fetch = vi.fn(() => new Promise<Response>(done => { resolve = done; })); vi.stubGlobal("fetch", fetch);
  const { rerender } = render(<DocumentCover item={resource} />);
  expect(fetch).not.toHaveBeenCalled();
  act(() => intersect([{ isIntersecting: false }]));
  expect(fetch).not.toHaveBeenCalled();
  act(() => { intersect([{ isIntersecting: true }]); intersect([{ isIntersecting: true }]); });
  expect(fetch).toHaveBeenCalledTimes(1);
  rerender(<DocumentCover item={{ ...resource, preview_ready: false }} />);
  await act(async () => resolve(Response.json(content)));
  expect(document.querySelector(".library-preview")).toBeNull();
  expect(disconnect).toHaveBeenCalled();
});

function Receipt({ rendered, version, ready }: { rendered: boolean; version?: string; ready: () => void }) {
  usePreviewReady(resource.id, version, "csrf", rendered, ready); return null;
}

test("render receipts follow saved revisions and never upload document HTML or drafts", async () => {
  const fetch = vi.fn(async (request: Request) => {
    expect(request.method).toBe("POST");
    expect(await request.json()).toEqual({ source_version_id: resource.current_version_id });
    return Response.json(resource);
  }); vi.stubGlobal("fetch", fetch);
  const ready = vi.fn();
  const { rerender } = render(<Receipt rendered={false} version={resource.current_version_id} ready={ready} />);
  expect(fetch).not.toHaveBeenCalled();
  rerender(<Receipt rendered version={resource.current_version_id} ready={ready} />);
  await waitFor(() => expect(ready).toHaveBeenCalledTimes(1));
  rerender(<Receipt rendered version={resource.current_version_id} ready={ready} />);
  expect(fetch).toHaveBeenCalledTimes(1);
});

test.each([false, true])("failed render receipts are nonfatal (network=%s)", async network => {
  vi.stubGlobal("fetch", vi.fn(async () => { if (network) throw new Error("offline"); return Response.json({error:{code:"not_found",parameters:{}}},{status:404}); }));
  const ready = vi.fn();
  await act(async () => { render(<Receipt rendered version={resource.current_version_id} ready={ready} />); });
  expect(ready).not.toHaveBeenCalled();
});
