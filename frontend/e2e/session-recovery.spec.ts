import { manualSaving } from "./autosave-setting";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  const anonymous = await (await page.request.get("/api/auth/session")).json();
  const login = await page.request.post("/api/auth/login", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": anonymous.csrf_token },
    data: { login: "library@example.test", password: "Synthetic-browser-Їжак-2026" },
  });
  expect(login.status()).toBe(200);
  const session = await login.json();
  const uploaded = await page.request.post("/api/documents", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": session.csrf_token,
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Idempotency-Key": randomUUID(),
      "X-Upload-Metadata": Buffer.from(JSON.stringify({ kind: "document", filename: "Анкета-Їжак.docx", title: "Відновлення сесії Ґанни" })).toString("base64") },
    data: await readFile("/fixtures/upload.docx"),
  });
  expect(uploaded.status()).toBe(201);
  const resource = await uploaded.json();
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await manualSaving(page);
  return { resource, endpoint: `/api/documents/${resource.id}` };
}

const value = (page: Page) => page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }).first();
const editor = (page: Page) => page.getByRole("textbox", { name: "Редагований документ", exact: true });

test("revoked sessions and missing cookies retain the same draft and editor through sign-in and explicit discard cancellation", async ({ page, context }, info) => {
  test.setTimeout(120000);
  const { endpoint } = await open(page), retained = await editor(page).elementHandle();
  await value(page).fill("Незбережена Ґанна 🙂");
  const active = await (await page.request.get("/api/auth/session")).json();
  expect((await page.request.post("/api/auth/logout", { headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": active.csrf_token } })).status()).toBe(200);
  await context.clearCookies({ name: "fillable_session_v1" });
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  const recovery = page.getByRole("region", { name: "Відновлення сесії", exact: true });
  await expect(recovery).toBeVisible();
  await expect(recovery.getByLabel("Пароль", { exact: true })).toBeVisible();
  expect(await retained!.evaluate(node => node.isConnected)).toBe(true);
  await page.screenshot({ path: info.outputPath("session-recovery-uk.png"), fullPage: true });
  page.once("dialog", dialog => dialog.dismiss());
  await recovery.getByRole("button", { name: "Залишити цей робочий простір та використати інший обліковий запис", exact: true }).click();
  await expect(recovery).toBeVisible();
  await recovery.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await recovery.getByRole("button", { name: "Увійти знову", exact: true }).click();
  await expect(recovery).not.toBeVisible();
  await page.getByRole("button", { name: "Повернутися до редагування", exact: true }).click();
  await expect(value(page)).toHaveValue("Незбережена Ґанна 🙂");
  expect(await editor(page).evaluate((node, original) => node === original, retained)).toBe(true);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible({ timeout: 15000 });
  await page.getByRole("button", { name: "Скасувати", exact: true }).click();
  await expect(value(page)).not.toHaveValue("Незбережена Ґанна 🙂");
  await page.getByRole("button", { name: "Повторити", exact: true }).click();
  await expect(value(page)).toHaveValue("Незбережена Ґанна 🙂");
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  expect((await (await page.request.get(`${endpoint}/versions`)).json()).items).toHaveLength(2);
  await page.reload(); await expect(value(page)).toHaveValue("Незбережена Ґанна 🙂");
});

test("a committed response from before recovery stays uncertain and retries its exact write", async ({ page, context }) => {
  test.setTimeout(90000);
  const { endpoint } = await open(page), retained = await editor(page).elementHandle();
  const writes: { key: string; body: object }[] = [];
  let release!: () => void, committed!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const arrived = new Promise<void>(resolve => { committed = resolve; });
  await page.route(`${endpoint}/versions`, async route => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    writes.push({ key: route.request().headers()["idempotency-key"], body: route.request().postDataJSON() });
    if (writes.length === 1) { const response = await route.fetch(); expect(response.status()).toBe(201); committed(); await gate; await route.fulfill({ response }); }
    else await route.continue();
  });
  await value(page).fill("Збережена перед відновленням Ґанна");
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click(); await arrived;
  const active = await (await page.request.get("/api/auth/session")).json();
  expect((await page.request.post("/api/auth/logout", { headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": active.csrf_token } })).status()).toBe(200);
  await context.clearCookies({ name: "fillable_session_v1" });
  // The next automatic lease renewal meets the revoked session and opens recovery.
  const recovery = page.getByRole("region", { name: "Відновлення сесії", exact: true });
  await expect(recovery).toBeVisible({ timeout: 30000 });
  await recovery.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await recovery.getByRole("button", { name: "Увійти знову", exact: true }).click();
  await expect(recovery).not.toBeVisible();
  release();
  await expect(page.getByText(/Результат збереження ще не підтверджено/)).toBeVisible();
  expect(await editor(page).evaluate((node, original) => node === original, retained)).toBe(true);
  await page.getByRole("button", { name: "Повторити збереження", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]);
  expect((await (await page.request.get(`${endpoint}/versions`)).json()).items).toHaveLength(2);
});

test("explicit recovery discard resolves unsaved work and a fresh account login adopts its language", async ({ page }, info) => {
  const { endpoint } = await open(page), retained = await editor(page).elementHandle();
  await value(page).fill("Приватна незбережена Ґанна");
  const current = await (await page.request.get("/api/auth/session")).json();
  expect((await page.request.post("/api/auth/logout", { headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": current.csrf_token } })).status()).toBe(200);
  await page.context().clearCookies({ name: "fillable_session_v1" });
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  const recovery = page.getByRole("region", { name: "Відновлення сесії", exact: true });
  await expect(recovery).toBeVisible();
  expect(await retained!.evaluate(node => node.isConnected)).toBe(true);
  const discard = recovery.getByRole("button", { name: "Залишити цей робочий простір та використати інший обліковий запис", exact: true });
  page.once("dialog", dialog => dialog.dismiss()); await discard.click();
  await expect(recovery).toBeVisible();
  page.once("dialog", dialog => dialog.accept()); await discard.click();
  expect(await retained!.evaluate(node => node.isConnected)).toBe(false);
  // A fresh login as the English account adopts its saved language.
  await page.getByLabel("Логін", { exact: true }).fill("browser-user");
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  await expect(page.getByRole("link", { name: "Profile", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/documents$/);
  expect((await page.request.get(endpoint)).status()).toBe(404);
  // Exercise the English recovery layout after an explicit logout in another tab.
  const active = await (await page.request.get("/api/auth/session")).json();
  expect((await page.request.post("/api/auth/logout", { headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": active.csrf_token } })).status()).toBe(200);
  await page.getByRole("button", { name: "Refresh library", exact: true }).click();
  const enRecovery = page.getByRole("region", { name: "Restore your session", exact: true });
  await expect(enRecovery.getByLabel("Password", { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("session-recovery-en.png"), fullPage: true });
  await enRecovery.getByLabel("Password", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await enRecovery.getByRole("button", { name: "Sign in again", exact: true }).click();
  await expect(enRecovery).not.toBeVisible();
  expect((await (await page.request.get("/api/auth/session")).json()).user.login).toBe("browser-user");
});
