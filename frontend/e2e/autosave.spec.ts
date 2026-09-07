import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  const anonymous = await (await page.request.get("/api/auth/session")).json();
  const response = await page.request.post("/api/auth/login", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": anonymous.csrf_token },
    data: { email: "library@example.test", password: "Synthetic-browser-Їжак-2026" },
  });
  expect(response.status()).toBe(200); const session = await response.json();
  const upload = await page.request.post("/api/documents", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": session.csrf_token,
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Idempotency-Key": randomUUID(),
      "X-Upload-Metadata": Buffer.from(JSON.stringify({ kind: "document", filename: "Автозбереження-Їжак.docx", title: "Автозбереження Ґанни" })).toString("base64") },
    data: await readFile("/fixtures/upload.docx"),
  });
  expect(upload.status()).toBe(201); const resource = await upload.json();
  const endpoint = `/api/documents/${resource.id}`;
  const writes: { key: string; body: { document: object } }[] = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname === `${endpoint}/versions` && request.method() === "POST")
      writes.push({ key: request.headers()["idempotency-key"], body: request.postDataJSON() });
  });
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  return { resource, endpoint, writes };
}
const values = (page: Page) => page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true });
const saved = (page: Page) => expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible({ timeout: 10000 });
const idle = (page: Page) => page.waitForTimeout(2300);

test("default autosave debounces edits, preserves the editor across locale, and obeys its workspace toggle", async ({ page }, info) => {
  test.setTimeout(90000);
  const { endpoint, writes } = await open(page);
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true }), retained = await editor.elementHandle();
  await expect(page.locator(".workspace-discovery")).toContainText("Перевірку завершено", { timeout: 20000 });
  await idle(page); expect(writes).toHaveLength(0);
  await values(page).first().fill("Перша Ґанна"); await page.waitForTimeout(300);
  await values(page).first().fill("Остання Єва 🙂"); await saved(page); expect(writes).toHaveLength(1);
  expect((await (await page.request.get(`${endpoint}/versions`)).json()).items).toHaveLength(2);
  expect(await editor.evaluate((node, original) => node === original, retained)).toBe(true);
  await page.getByText("Налаштування робочого простору", { exact: true }).click();
  const toggle = page.getByRole("checkbox", { name: "Автозбереження документа", exact: true });
  await expect(toggle).toBeChecked(); await toggle.uncheck();
  await values(page).first().fill("Ручна чернетка Їжака"); await idle(page); expect(writes).toHaveLength(1);
  await toggle.check(); await saved(page); expect(writes).toHaveLength(2);
  await page.getByRole("textbox", { name: "Назва", exact: true }).fill("Окрема назва чернетки");
  await idle(page); expect(writes).toHaveLength(2);
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await page.getByRole("combobox", { name: "Мова інтерфейсу", exact: true }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову", exact: true }).click();
  await page.getByRole("link", { name: "Document workspace", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "Autosave document", exact: true })).toBeChecked();
  expect(await page.getByRole("textbox", { name: "Editable document", exact: true }).evaluate((node, original) => node === original, retained)).toBe(true);
  await page.screenshot({ path: info.outputPath("autosave-settings-en.png"), fullPage: true });
  expect(writes).toHaveLength(2);
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("combobox", { name: "Interface language", exact: true }).selectOption("uk");
  await page.getByRole("button", { name: "Save language", exact: true }).click();
  await expect(page.getByRole("link", { name: "Профіль", exact: true })).toBeVisible();
});

test("native composition and historical previews never save provisional or historical content", async ({ page, context }, info) => {
  test.setTimeout(90000);
  const { resource, endpoint, writes } = await open(page);
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true }), retained = await editor.elementHandle();
  await page.getByRole("button", { name: "Перейти до поля: ПІБ клієнта", exact: true }).last().click();
  const cdp = await context.newCDPSession(page), final = "Ґанна Їжак 🙂";
  await cdp.send("Input.imeSetComposition", { text: final, selectionStart: final.length, selectionEnd: final.length });
  await idle(page); expect(writes).toHaveLength(0);
  await cdp.send("Input.insertText", { text: final }); await saved(page); expect(writes).toHaveLength(1);
  await expect(values(page).first()).toHaveValue(final);
  await values(page).first().fill("Чернетка під час історії");
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  await page.getByRole("button", { name: /^Версія 1/ }).click();
  await expect(page.getByRole("heading", { name: "Версія 1", exact: true })).toBeVisible();
  const preview = page.getByRole("textbox", { name: "Історична версія документа лише для читання", exact: true });
  await expect(preview).not.toContainText(final); await preview.click(); await page.keyboard.insertText("Не зберігати");
  await idle(page); expect(writes).toHaveLength(1);
  await expect(preview).not.toContainText("Не зберігати");
  expect((await (await page.request.get(`${endpoint}/versions`)).json()).items).toHaveLength(2);
  await page.screenshot({ path: info.outputPath("autosave-history-paused-uk.png"), fullPage: true });
  await page.getByRole("button", { name: "Повернутися до редагування", exact: true }).click();
  expect(await editor.evaluate((node, original) => node === original, retained)).toBe(true);
  await saved(page); expect(writes).toHaveLength(2);
  expect((await (await page.request.get(endpoint)).json()).current_version_id).not.toBe(resource.current_version_id);
  await page.reload(); await expect(values(page).first()).toHaveValue("Чернетка під час історії");
  await cdp.detach();
});

test("an uncertain autosave pauses retries and preserves newer typing until exact retry then a separate save", async ({ page }, info) => {
  test.setTimeout(90000);
  const { endpoint, writes } = await open(page);
  let count = 0;
  await page.route(`${endpoint}/versions`, async route => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    count += 1;
    if (count === 1) { const response = await route.fetch(); expect(response.status()).toBe(201); await route.abort(); }
    else if (count === 4) await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "quota_exceeded" } }) });
    else await route.continue();
  });
  await values(page).first().fill("Перша збережена Ґанна");
  await expect(page.getByText(/Результат збереження ще не підтверджено/)).toBeVisible({ timeout: 10000 });
  await values(page).first().fill("Новіша чернетка Єви"); await idle(page); expect(writes).toHaveLength(1);
  // The worker's shared read lock can legitimately make a committed retry busy.
  // Wait for that real reader to finish; pending saves still require a manual retry.
  await expect.poll(async () => (await (await page.request.get(`${endpoint}/processing`)).json()).status,
    { timeout: 20000 }).toBe("succeeded");
  expect(writes).toHaveLength(1);
  await page.getByRole("button", { name: "Повторити збереження", exact: true }).click();
  await saved(page); expect(writes).toHaveLength(3); expect(writes[1]).toEqual(writes[0]); expect(writes[2].key).not.toBe(writes[0].key);
  expect((await (await page.request.get(`${endpoint}/versions`)).json()).items).toHaveLength(3);
  await values(page).first().fill("Чернетка без місця");
  await expect(page.getByText("Недостатньо доступного місця в сховищі для збереження файла.", { exact: true })).toBeVisible({ timeout: 10000 });
  await values(page).first().fill("Ще новіша чернетка"); await idle(page); expect(writes).toHaveLength(4);
  await page.screenshot({ path: info.outputPath("autosave-quota-uk.png"), fullPage: true });
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click(); await saved(page); expect(writes).toHaveLength(5);
  await expect(values(page).first()).toHaveValue("Ще новіша чернетка");
});
