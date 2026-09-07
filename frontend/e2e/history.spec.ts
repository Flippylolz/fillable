import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page, kind: "template" | "document") {
  await page.goto("/");
  await expect(page.getByLabel("Пароль", { exact: true })).toBeVisible();
  const anonymous = await (await page.request.get("/api/auth/session")).json();
  const login = await page.request.post("/api/auth/login", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": anonymous.csrf_token },
    data: { email: "library@example.test", password: "Synthetic-browser-Їжак-2026" },
  });
  expect(login.status()).toBe(200);
  const session = await login.json();
  const uploaded = await page.request.post("/api/documents", {
    headers: { Origin: new URL(page.url()).origin, "X-CSRF-Token": session.csrf_token,
      "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Idempotency-Key": randomUUID(),
      "X-Upload-Metadata": Buffer.from(JSON.stringify({ kind, filename: "Історія-Їжак.docx", title: `Історія Ґанни ${kind}` })).toString("base64") },
    data: await readFile("/fixtures/upload.docx"),
  });
  expect(uploaded.status()).toBe(201);
  const resource = await uploaded.json(), endpoint = `/api/documents/${resource.id}`;
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  return { resource, endpoint };
}

for (const kind of ["template", "document"] as const) test(`${kind} history preserves drafts, downloads exact original and restores through the panel`, async ({ page }, testInfo) => {
  test.setTimeout(60000);
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  const { resource, endpoint } = await open(page, kind);
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true });
  const retained = await editor.elementHandle();
  const values = page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true });
  await values.first().fill("Збережена Ґанна Їжак");
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  const second = await (await page.request.get(endpoint)).json();
  expect(second.current_version_id).not.toBe(resource.current_version_id);
  await values.first().fill("Незбережена Єва 🙂");
  await page.getByText("Налаштування робочого простору", { exact: true }).click();
  await page.getByRole("textbox", { name: "Назва", exact: true }).fill("Назва моєї чернетки");
  const usage = await (await page.request.get("/api/storage/usage")).json();
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  const panel = page.getByRole("region", { name: "Історія версій", exact: true });
  await expect(panel.getByText(/Вашу незбережену чернетку збережено/)).toBeVisible();
  await panel.getByRole("button", { name: /^Версія 1/ }).click();
  const preview = page.getByRole("textbox", { name: "Історична версія документа лише для читання", exact: true });
  await expect(preview).toBeVisible(); await expect(preview).toHaveAttribute("aria-readonly", "true");
  await expect(preview).toHaveAttribute("contenteditable", "false");
  await expect(preview).not.toContainText("Збережена Ґанна Їжак");
  await preview.locator("p").first().click(); await page.keyboard.insertText("Не змінювати історію");
  await expect(preview).not.toContainText("Не змінювати історію");
  const downloadPromise = page.waitForEvent("download");
  await panel.getByRole("button", { name: "Завантажити цю версію DOCX", exact: true }).click();
  const download = await downloadPromise;
  await download.saveAs(testInfo.outputPath("history-original.docx"));
  expect(await readFile(testInfo.outputPath("history-original.docx"))).toEqual(await readFile("/fixtures/upload.docx"));
  expect(await (await page.request.get("/api/storage/usage")).json()).toEqual(usage);
  const policy = (await (await page.request.get(`${endpoint}/versions`)).json()).retention;
  await expect(panel.locator(".history-policy")).toContainText(policy.keep_latest === null
    ? "Усі збережені версії зберігаються" : `останні ${policy.keep_latest} версії`);
  await page.screenshot({ path: testInfo.outputPath("history-uk.png"), fullPage: true });
  await page.getByRole("button", { name: "Повернутися до редагування", exact: true }).click();
  expect(await editor.evaluate((node, original) => node === original, retained)).toBe(true);
  await expect(values.first()).toHaveValue("Незбережена Єва 🙂");
  await expect(page.getByRole("textbox", { name: "Назва", exact: true })).toHaveValue("Назва моєї чернетки");
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  await panel.getByRole("button", { name: /^Версія 1/ }).click();
  await expect(preview).toBeVisible();
  page.once("dialog", dialog => dialog.dismiss());
  await panel.getByRole("button", { name: "Відновити як нову версію", exact: true }).click();
  expect((await (await page.request.get(endpoint)).json()).current_version_id).toBe(second.current_version_id);
  page.once("dialog", dialog => dialog.accept());
  await panel.getByRole("button", { name: "Відновити як нову версію", exact: true }).click();
  await expect(page.getByRole("button", { name: "Історія версій", exact: true })).toBeVisible();
  await expect(editor).not.toContainText("Незбережена Єва 🙂");
  expect(await (await page.request.get(`${endpoint}/download`)).body()).toEqual(await readFile("/fixtures/upload.docx"));
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  await expect(panel.getByText("Відновлено з версії 1", { exact: true })).toBeVisible();
  await expect(panel.getByRole("button", { name: /^Версія 2/ })).toBeVisible();
  await expect(panel.getByRole("button", { name: /^Версія 3/ })).toContainText("Поточна версія");
  expect(errors).toEqual([]);
});

test("uncertain restore survives newer draft and locale; quota failure keeps history and draft", async ({ page }, testInfo) => {
  test.setTimeout(60000);
  const { endpoint } = await open(page, "document");
  const values = page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true });
  await values.first().fill("Збережена версія Їжака");
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  await values.first().fill("Чернетка перед відновленням");
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true });
  const retained = await editor.elementHandle();
  await page.getByRole("button", { name: "Історія версій", exact: true }).click();
  const panel = page.getByRole("region", { name: "Історія версій", exact: true });
  await panel.getByRole("button", { name: /^Версія 1/ }).click();
  await expect(page.getByRole("textbox", { name: "Історична версія документа лише для читання", exact: true })).toBeVisible();
  const requests: { key: string; body: object }[] = [];
  await page.route(`${endpoint}/versions/*/restore`, async route => {
    requests.push({ key: route.request().headers()["idempotency-key"], body: route.request().postDataJSON() });
    if (requests.length === 1) {
      const response = await route.fetch(); expect(response.status()).toBe(201); await route.abort();
    } else if (requests.length === 3) {
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ error: { code: "quota_exceeded" } }) });
    } else await route.continue();
  });
  page.once("dialog", dialog => dialog.accept());
  await panel.getByRole("button", { name: "Відновити як нову версію", exact: true }).click();
  await expect(page.getByText(/Результат ще не підтверджено/)).toBeVisible();
  await page.getByRole("button", { name: "Повернутися до редагування", exact: true }).click();
  await expect(values.first()).toHaveValue("Чернетка перед відновленням");
  await values.first().fill("Новіша чернетка Єви 🙂");
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await page.getByRole("combobox", { name: "Мова інтерфейсу", exact: true }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову", exact: true }).click();
  await page.getByRole("link", { name: "Document workspace", exact: true }).click();
  const englishEditor = page.getByRole("textbox", { name: "Editable document", exact: true });
  expect(await englishEditor.evaluate((node, original) => node === original, retained)).toBe(true);
  await expect(englishEditor).toContainText("Новіша чернетка Єви 🙂");
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Retry restoring version 1", exact: true }).click();
  await expect(page.getByText("Editing enabled.", { exact: true })).toBeVisible();
  await expect(englishEditor).not.toContainText("Новіша чернетка Єви 🙂");
  expect(requests[1]).toEqual(requests[0]);
  await page.getByRole("textbox", { name: "Field value: ПІБ клієнта", exact: true }).first().fill("Чернетка після відновлення");
  const current = await (await page.request.get(endpoint)).json();
  await page.getByRole("button", { name: "Version history", exact: true }).click();
  const englishPanel = page.getByRole("region", { name: "Version history", exact: true });
  await englishPanel.getByRole("button", { name: /^Version 2/ }).click();
  await expect(page.getByRole("textbox", { name: "Read-only historical document", exact: true })).toContainText("Збережена версія Їжака");
  page.once("dialog", dialog => dialog.accept());
  await englishPanel.getByRole("button", { name: "Restore as a new revision", exact: true }).click();
  await expect(page.getByText("There is not enough storage allowance to save this file.", { exact: true })).toBeVisible();
  expect((await (await page.request.get(endpoint)).json()).current_version_id).toBe(current.current_version_id);
  const policy = (await (await page.request.get(`${endpoint}/versions`)).json()).retention;
  await expect(englishPanel.locator(".history-policy")).toContainText(policy.keep_latest === null
    ? "All saved revisions are retained" : `the latest ${policy.keep_latest} revisions are kept`);
  await page.screenshot({ path: testInfo.outputPath("history-quota-en.png"), fullPage: true });
  await page.getByRole("button", { name: "Return to editing", exact: true }).click();
  await expect(englishEditor).toContainText("Чернетка після відновлення");
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("combobox", { name: "Interface language", exact: true }).selectOption("uk");
  await page.getByRole("button", { name: "Save language", exact: true }).click();
  await expect(page.getByRole("link", { name: "Профіль", exact: true })).toBeVisible();
});
