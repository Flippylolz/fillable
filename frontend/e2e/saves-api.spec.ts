import { randomUUID } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { expect, test, type Page, type TestInfo } from "@playwright/test";

async function start(page: Page, testInfo: TestInfo) {
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  const origin = new URL(page.url()).origin;
  const anonymous = await (await page.request.get("/api/auth/session")).json();
  const login = await page.request.post("/api/auth/login", {
    headers: { Origin: origin, "X-CSRF-Token": anonymous.csrf_token },
    data: { email: "library@example.test", password: "Synthetic-browser-Їжак-2026" },
  });
  expect(login.status()).toBe(200);
  const session = await login.json();
  const headers = { Origin: origin, "X-CSRF-Token": session.csrf_token };
  const uploaded = await page.request.post("/api/documents", {
    headers: { ...headers, "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Idempotency-Key": randomUUID(), "X-Upload-Metadata": Buffer.from(JSON.stringify({
        kind: "template", filename: "Їжак.docx", title: `Збереження через API ${testInfo.project.name}`,
      })).toString("base64") }, data: await readFile("/fixtures/upload.docx"),
  });
  expect(uploaded.status()).toBe(201);
  const resource = await uploaded.json(), client = randomUUID();
  const endpoint = `/api/documents/${resource.id}`;
  const acquired = await page.request.post(`${endpoint}/editing-lease`, {
    headers, data: { action: "acquire", client_id: client, source_version_id: resource.current_version_id },
  });
  expect(acquired.status()).toBe(200);
  const lease = await acquired.json();
  return { headers, resource, client, endpoint, lease };
}

test("saved API revision reopens matching review through the real gateway", async ({ page }, testInfo) => {
  const { headers, resource, client, endpoint, lease } = await start(page, testInfo);
  const document = JSON.parse(await readFile("/fixtures/working-review.json", "utf8"));
  document.attrs.review.sourceVersion = resource.current_version_id;
  const request = { document, source_version_id: resource.current_version_id, client_id: client, lease_id: lease.lease_id };
  const operation = randomUUID();
  const response = await page.request.post(`${endpoint}/versions`, { headers: { ...headers, "Idempotency-Key": operation }, data: request });
  expect(response.status()).toBe(201);
  const saved = await response.json();
  expect(saved.saved_version_id).toBe(saved.resource.current_version_id);
  expect(saved.saved_number).toBe(2);
  // Real proxy route admits bounded save JSON beyond the older upload-body limit.
  const retried = await page.request.post(`${endpoint}/versions`, {
    headers: { ...headers, "Idempotency-Key": operation, "Content-Type": "application/json" },
    data: JSON.stringify(request) + " ".repeat(25 * 1024 * 1024),
  });
  expect(retried.status()).toBe(201);
  expect((await retried.json()).saved_version_id).toBe(saved.saved_version_id);
  expect((await (await page.request.get(`${endpoint}/content`)).json()).document).toEqual(document);
  const downloaded = await page.request.get(`${endpoint}/download`);
  expect(downloaded.headers()["x-fillable-version"]).toBe(saved.saved_version_id);
  await writeFile(testInfo.outputPath("saved-api.docx"), await downloaded.body());
  const history = await (await page.request.get(`${endpoint}/versions`)).json();
  expect(history.items.map((item: { number: number }) => item.number)).toEqual([2, 1]);
  const historical = await page.request.get(`${endpoint}/versions/${resource.current_version_id}/download`);
  expect(historical.status()).toBe(200);
  expect(historical.headers()["x-fillable-version"]).toBe(resource.current_version_id);
  expect(historical.headers()["cache-control"]).toBe("no-store");
  expect(await historical.body()).toEqual(await readFile("/fixtures/upload.docx"));
  expect(await historical.body()).not.toEqual(await downloaded.body());
  const exactSaved = await page.request.get(`${endpoint}/versions/${saved.saved_version_id}/download`);
  expect(exactSaved.headers()["x-fillable-version"]).toBe(saved.saved_version_id);
  expect(await exactSaved.body()).toEqual(await downloaded.body());
  await writeFile(testInfo.outputPath("historical-original.docx"), await historical.body());

  const released = await page.request.post(`${endpoint}/editing-lease`, {
    headers, data: { action: "release", client_id: client, source_version_id: saved.saved_version_id, lease_id: lease.lease_id },
  });
  expect(released.status()).toBe(200);
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Значення поля: Заголовок Ґанни", exact: true })).toHaveValue("АНКЕТА");
  await expect(page.getByRole("textbox", { name: "Редагований документ", exact: true })).toContainText("Ґанна Їжак 🙂");
  await page.screenshot({ path: testInfo.outputPath("saved-api-reopened.png"), fullPage: true });
});


test("local unbound review is bound on save and reopens without stale detection", async ({ page }, testInfo) => {
  const { headers, resource, client, endpoint, lease } = await start(page, testInfo);
  const document = (await (await page.request.get(`${endpoint}/content`)).json()).document;
  const nodes = [document], items = [];
  while (nodes.length) {
    const node = nodes.pop()!;
    nodes.push(...(node.content ?? []));
    if (node.type === "field") items.push({ id: `candidate:${node.attrs.id}`, occurrenceId: node.attrs.id,
      reason: "native_control", sourceKey: node.attrs.key, context: "", label: node.attrs.label, key: node.attrs.key,
      type: "text", decision: "accepted", missing: false, location: { kind: "control", id: node.attrs.id } });
  }
  document.attrs = { review: { sourceVersion: null, items } };
  const response = await page.request.post(`${endpoint}/versions`, {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: { document, source_version_id: resource.current_version_id, client_id: client, lease_id: lease.lease_id },
  });
  expect(response.status()).toBe(201);
  const saved = await response.json();
  expect((await (await page.request.get(`${endpoint}/content`)).json()).document.attrs.review)
    .toEqual({ sourceVersion: resource.current_version_id, items });
  expect(await (await page.request.get(`${endpoint}/download`)).body()).toEqual(await readFile("/fixtures/upload.docx"));
  await page.request.post(`${endpoint}/editing-lease`, {
    headers, data: { action: "release", client_id: client, source_version_id: saved.saved_version_id, lease_id: lease.lease_id },
  });
  await page.goto(`/editor/${resource.id}`);
  await expect(page.locator(".workspace-discovery").getByText("Перевірку завершено", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole("textbox", { name: "Редагований документ", exact: true })).toBeVisible();
  await expect(page.getByText("Ці пропозиції стосуються збереженого документа. Чернетку змінено; відкрийте збережений документ знову, щоб перевірити їх.", { exact: true })).toHaveCount(0);
});

test("historical restore creates new exact revisions and reopens reviewed fields", async ({ page }, testInfo) => {
  const { headers, resource, client, endpoint, lease } = await start(page, testInfo);
  const document = JSON.parse(await readFile("/fixtures/working-review.json", "utf8"));
  document.attrs.review.sourceVersion = resource.current_version_id;
  const savedResponse = await page.request.post(`${endpoint}/versions`, {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: { document, source_version_id: resource.current_version_id, client_id: client, lease_id: lease.lease_id },
  });
  expect(savedResponse.status()).toBe(201);
  const saved = await savedResponse.json();
  const edited = await (await page.request.get(`${endpoint}/download`)).body();
  const restoreHeaders = { ...headers, "Idempotency-Key": randomUUID() };
  const firstBody = { source_version_id: saved.saved_version_id, client_id: client, lease_id: lease.lease_id };
  const originalRestore = await page.request.post(`${endpoint}/versions/${resource.current_version_id}/restore`, {
    headers: restoreHeaders, data: firstBody,
  });
  expect(originalRestore.status()).toBe(201);
  const original = await originalRestore.json();
  expect(original.saved_number).toBe(3);
  expect(await (await page.request.get(`${endpoint}/download`)).body()).toEqual(await readFile("/fixtures/upload.docx"));
  const reviewedRestore = await page.request.post(`${endpoint}/versions/${saved.saved_version_id}/restore`, {
    headers: { ...headers, "Idempotency-Key": randomUUID() },
    data: { ...firstBody, source_version_id: original.saved_version_id },
  });
  expect(reviewedRestore.status()).toBe(201);
  const restored = await reviewedRestore.json();
  expect(restored.saved_number).toBe(4);
  const replay = await page.request.post(`${endpoint}/versions/${resource.current_version_id}/restore`, {
    headers: restoreHeaders, data: firstBody,
  });
  expect(replay.status()).toBe(201);
  expect((await replay.json()).saved_version_id).toBe(original.saved_version_id);
  expect((await replay.json()).resource.current_version_id).toBe(restored.saved_version_id);
  const history = await (await page.request.get(`${endpoint}/versions`)).json();
  expect(history.items.map((item: { number: number }) => item.number)).toEqual([4, 3, 2, 1]);
  expect(history.items[0]).toMatchObject({ parent_version_id: original.saved_version_id,
    restored_from_version_id: saved.saved_version_id, restored_from_number: 2 });
  expect((await (await page.request.get(`${endpoint}/content`)).json()).document).toEqual(document);
  const downloaded = await page.request.get(`${endpoint}/download`);
  expect(downloaded.headers()["x-fillable-version"]).toBe(restored.saved_version_id);
  expect(await downloaded.body()).toEqual(edited);
  await writeFile(testInfo.outputPath("restored-reviewed.docx"), await downloaded.body());
  await page.request.post(`${endpoint}/editing-lease`, {
    headers, data: { action: "release", client_id: client, source_version_id: restored.saved_version_id, lease_id: lease.lease_id },
  });
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Значення поля: Заголовок Ґанни", exact: true })).toHaveValue("АНКЕТА");
  await expect(page.getByRole("textbox", { name: "Редагований документ", exact: true })).toContainText("Ґанна Їжак 🙂");
  await page.screenshot({ path: testInfo.outputPath("restored-reviewed.png"), fullPage: true });
});
