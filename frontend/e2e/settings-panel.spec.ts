import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  const anonymous = await (await page.request.get("/api/auth/session")).json();
  const response = await page.request.post("/api/auth/login", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": anonymous.csrf_token },
    data: { login: "library@example.test", password: "Synthetic-browser-Їжак-2026" },
  });
  expect(response.status()).toBe(200); const session = await response.json();
  const upload = await page.request.post("/api/documents", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": session.csrf_token,
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Idempotency-Key": randomUUID(),
      "X-Upload-Metadata": Buffer.from(JSON.stringify({ kind: "document", filename: "Панель-Їжак.docx", title: "Панель налаштувань Ґанни" })).toString("base64") },
    data: await readFile("/fixtures/upload.docx"),
  });
  expect(upload.status()).toBe(201); const resource = await upload.json();
  const endpoint = `/api/documents/${resource.id}`;
  const writes: string[] = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname === `${endpoint}/versions` && request.method() === "POST")
      writes.push(request.headers()["idempotency-key"]);
  });
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await expect(page.locator(".workspace-discovery")).toContainText("Перевірку завершено", { timeout: 20000 });
  return { endpoint, writes };
}
const value = (page: Page) => page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }).first();
const draft = "Чернетка назви Ґанни";

test("workspace settings stay open with their draft across autosaves and lease renewals", async ({ page }, info) => {
  test.setTimeout(150000);
  const { writes } = await open(page);
  const renewals: { action?: string }[] = [];
  page.on("request", request => {
    if (request.method() === "POST" && new URL(request.url()).pathname.endsWith("/editing-lease")) {
      try { const body = request.postDataJSON(); if (body?.action === "renew") renewals.push(body); } catch { /* body unavailable */ }
    }
  });
  const settings = page.locator(".workspace-settings");
  await page.getByText("Налаштування робочого простору", { exact: true }).click();
  const title = page.getByRole("textbox", { name: "Назва", exact: true });
  await title.fill(draft);
  await value(page).fill("Панель-Їжак");
  // The title draft intentionally keeps the workspace marked unsaved; watch the save requests instead.
  const isOpen = () => settings.evaluate(node => (node as HTMLDetailsElement).open);
  await expect.poll(() => writes.length, { timeout: 15000 }).toBeGreaterThanOrEqual(1);
  expect(await isOpen()).toBe(true);
  // Hold the panel open for 60+ seconds while the lease renews (every 20 s) and a second autosave lands.
  await page.waitForTimeout(20000);
  await value(page).fill("Панель-Єва 🙂");
  await expect.poll(() => writes.length, { timeout: 15000 }).toBeGreaterThanOrEqual(2);
  await page.waitForTimeout(42000);
  expect(await isOpen()).toBe(true);
  await expect(title).toBeVisible();
  await expect(title).toHaveValue(draft);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  expect(renewals.length).toBeGreaterThanOrEqual(2);
  expect(writes.length).toBeGreaterThanOrEqual(2);
  await page.screenshot({ path: info.outputPath("settings-panel-held-open.png"), fullPage: true });
});
