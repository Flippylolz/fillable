import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { Workspace } from "../src/workspace/Workspace";
import { i18n, setLanguage } from "../src/i18n";
import corpus from "../prototype/document.json";
import snapshot from "../prototype/fields.json";

const resource = { id: "11111111-1111-4111-8111-111111111111", kind: "template", title: "Saved source",
  original_filename: "source.docx", current_version_id: snapshot.source_version_id, size_bytes: 123,
  digest: "digest", unsupported_count: 1, deletion_pending: false, processing_status: "not_started" };
function Host() {
  const [dirty, setDirty] = useState(false);
  return <I18nextProvider i18n={i18n}><Workspace identity={resource.id} csrfToken="csrf" dirty={dirty} onDirty={setDirty} /></I18nextProvider>;
}

test("workspace starts legacy detection, retries failures and guards reopening an edited draft", async () => {
  await setLanguage("en");
  let reads = 0, starts = 0, opens = 0;
  const fetcher = vi.fn(async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path.endsWith("/content")) { opens++; return Response.json({ resource, document: corpus }); }
    if (request.method === "POST") {
      expect(request.headers.get("X-CSRF-Token")).toBe("csrf");
      if (++starts === 2) return Response.json({ error: { code: "dependencies_unavailable" } }, { status: 503 });
      return Response.json({ status: "queued", source_version_id: snapshot.source_version_id });
    }
    const status = ["not_started", "failed", "succeeded", "succeeded"][reads++];
    return Response.json({ status, source_version_id: reads === 3 ? "new-version" : snapshot.source_version_id,
      snapshot: status === "succeeded" ? snapshot : null });
  });
  vi.stubGlobal("fetch", fetcher);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<Host />);
  await screen.findByRole("button", { name: "Inspect document" });
  const value = (await screen.findAllByRole("textbox", { name: "Field value: ПІБ клієнта" }))[0];
  fireEvent.change(value, { target: { value: "Keep my draft" } });
  fireEvent.click(screen.getByRole("button", { name: "Inspect document" }));
  fireEvent.click(await screen.findByRole("button", { name: "Retry inspection" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry status check" }));
  fireEvent.click(await screen.findByRole("button", { name: "Reopen saved document" }));
  expect(value).toHaveValue("Keep my draft"); expect(opens).toBe(1);
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole("button", { name: "Reopen saved document" }));
  await screen.findByText("Review fields");
  expect(opens).toBe(2); expect(confirm).toHaveBeenCalledTimes(2);
  expect(screen.getByText("Saved revision opened.")).toBeVisible();
  expect(screen.getAllByRole("textbox", { name: "Field value: ПІБ клієнта" })[0]).not.toHaveValue("Keep my draft");
});
