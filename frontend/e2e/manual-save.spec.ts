import { manualSaving } from "./autosave-setting";
import { randomUUID } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page, kind: "template" | "document") {
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
      "X-Upload-Metadata": Buffer.from(JSON.stringify({ kind, filename: "Анкета-Їжак.docx", title: `Збереження Ґанни ${kind}` })).toString("base64") },
    data: await readFile("/fixtures/upload.docx"),
  });
  expect(uploaded.status()).toBe(201);
  const resource = await uploaded.json();
  await page.goto(`/editor/${resource.id}`);
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await manualSaving(page);
  return { resource, endpoint: `/api/documents/${resource.id}` };
}

test("manual saves acknowledge exact edits, retain title and history, and reopen the same reviewed DOCX", async ({ page }, testInfo) => {
  test.setTimeout(60000);
  const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
  // Exercise a local manual review before any asynchronous proposals attach.
  await page.route("**/api/documents/*/fields", route => route.abort());
  const { resource, endpoint } = await open(page, "template");
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true });
  const retained = await editor.elementHandle();
  const heading = editor.locator("p").first();
  await expect(heading).toHaveText("АНКЕТА КЛІЄНТА");
  await heading.click();
  // This save journey needs a native selection, not a timing-dependent global
  // Control+Home shortcut. Select the paragraph across all its source text runs
  // and wait for the browser event that the editor observes before blurring it.
  await heading.evaluate(async node => {
    const selectionChanged = new Promise<void>(resolve => {
      document.addEventListener("selectionchange", () => resolve(), { once: true });
    });
    window.getSelection()!.selectAllChildren(node);
    await selectionChanged;
  });
  await expect.poll(() => page.evaluate(() => window.getSelection()?.toString())).toBe("АНКЕТА КЛІЄНТА");
  await page.getByRole("textbox", { name: "Назва нового поля", exact: true }).fill("Заголовок Ґанни");
  await page.getByRole("button", { name: "Створити поле з виділення", exact: true }).click();
  await page.getByRole("textbox", { name: "Значення поля: Заголовок Ґанни", exact: true }).fill("Анкета Ґанни");
  const values = page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true });
  await values.first().fill("Перша Ґанна Їжак");
  let release!: () => void, committed!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  const arrived = new Promise<void>(resolve => { committed = resolve; });
  let first = true;
  await page.route(`${endpoint}/versions`, async route => {
    if (!first) { await route.continue(); return; }
    first = false;
    const response = await route.fetch(); expect(response.status()).toBe(201);
    committed(); await gate; await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await arrived;
  const firstSaved = await (await page.request.get(`${endpoint}/content`)).json();
  expect(firstSaved.document.attrs.review.sourceVersion).toBe(resource.current_version_id);
  await values.first().fill("Пізніша Єва Їжак 🙂");
  await page.getByText("Налаштування робочого простору", { exact: true }).click();
  await page.getByRole("textbox", { name: "Назва", exact: true }).fill("Анкета Ґанни — готова");
  await expect(page.getByRole("button", { name: "Перейменувати", exact: true })).toBeDisabled();
  release();
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Зберегти документ", exact: true })).toBeEnabled();
  await expect(page.locator(".workspace-save-state")).toContainText("Є незбережені зміни");
  await expect(values.first()).toHaveValue("Пізніша Єва Їжак 🙂");
  expect(await editor.evaluate((node, original) => node === original, retained)).toBe(true);
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByRole("button", { name: "Перейменувати", exact: true })).toBeEnabled();
  await expect(page.getByRole("textbox", { name: "Назва", exact: true })).toHaveValue("Анкета Ґанни — готова");
  await page.getByRole("button", { name: "Перейменувати", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  await page.unroute("**/api/documents/*/fields");
  await page.locator(".workspace-discovery").getByRole("button", { name: "Повторити запит стану", exact: true }).click();
  await expect(page.locator(".workspace-discovery")).toContainText("Перевірку завершено", { timeout: 15000 });
  await expect(page.getByText(/^Ці пропозиції стосуються збереженого документа/)).toHaveCount(0);
  await page.getByRole("button", { name: "Скасувати", exact: true }).click();
  await expect(page.locator(".workspace-save-state")).toContainText("Є незбережені зміни");
  await page.getByRole("button", { name: "Повторити", exact: true }).click();
  await expect(values.first()).toHaveValue("Пізніша Єва Їжак 🙂");
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText("Усі зміни документа збережено.", { exact: true })).toBeVisible();
  const saved = await (await page.request.get(`${endpoint}/content`)).json();
  const downloaded = await page.request.get(`${endpoint}/download`);
  expect(downloaded.headers()["x-fillable-version"]).toBe(saved.resource.current_version_id);
  await writeFile(testInfo.outputPath("manual-save.docx"), await downloaded.body());
  await writeFile(testInfo.outputPath("manual-save.json"), JSON.stringify(saved.document));
  await page.screenshot({ path: testInfo.outputPath("manual-save-uk.png"), fullPage: true });
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Значення поля: Заголовок Ґанни", exact: true })).toHaveValue("Анкета Ґанни");
  await expect(values.first()).toHaveValue("Пізніша Єва Їжак 🙂");
  expect((await (await page.request.get(`${endpoint}/content`)).json()).document).toEqual(saved.document);
  expect(errors).toEqual([]);
});

test("native composition, lost-response retry after lease pause and quota failure preserve the live draft", async ({ page, context }, testInfo) => {
  test.setTimeout(60000);
  await page.clock.install();
  const { endpoint } = await open(page, "document");
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true });
  const retained = await editor.elementHandle();
  await page.getByRole("button", { name: "Перейти до поля: ПІБ клієнта", exact: true }).last().click();
  const cdp = await context.newCDPSession(page);
  const value = "Ґанна Їжак 🙂";
  await cdp.send("Input.imeSetComposition", { text: value, selectionStart: value.length, selectionEnd: value.length });
  await expect(page.getByRole("button", { name: "Зберегти документ", exact: true })).toBeDisabled();
  await cdp.send("Input.insertText", { text: value });
  await expect(page.getByRole("button", { name: "Зберегти документ", exact: true })).toBeEnabled();
  const requests: { key: string; body: object }[] = [];
  let mode = "lost";
  await page.route(`${endpoint}/versions`, async route => {
    requests.push({ key: route.request().headers()["idempotency-key"], body: route.request().postDataJSON() });
    if (mode === "lost") { mode = "normal"; const result = await route.fetch(); expect(result.status()).toBe(201); await route.abort(); return; }
    if (mode === "quota") { mode = "normal"; await route.fulfill({ status: 409, json: { error: { code: "quota_exceeded" } } }); return; }
    await route.continue();
  });
  await page.getByRole("button", { name: "Зберегти документ", exact: true }).click();
  await expect(page.getByText(/^Результат збереження ще не підтверджено/)).toBeVisible();
  await page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true }).first().fill("Новіша чернетка Єви");
  await page.clock.fastForward(21000);
  await expect(page.getByText("Редагування призупинено. Чернетка залишається в цьому робочому просторі.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Повторити збереження", exact: true }).click();
  await expect(page.getByRole("button", { name: "Зберегти документ", exact: true })).toBeEnabled();
  expect(requests[1]).toEqual(requests[0]);
  await expect(page.locator(".workspace-save-state")).toContainText("Є незбережені зміни");
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await page.getByRole("combobox", { name: "Мова інтерфейсу", exact: true }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову", exact: true }).click();
  await page.getByRole("link", { name: "Document workspace", exact: true }).click();
  expect(await page.getByRole("textbox", { name: "Editable document", exact: true }).evaluate((node, original) => node === original, retained)).toBe(true);
  mode = "quota";
  const before = await (await page.request.get(`${endpoint}/content`)).json();
  await page.getByRole("button", { name: "Save document", exact: true }).click();
  await expect(page.locator(".workspace-save-error")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Field value: ПІБ клієнта", exact: true }).first()).toHaveValue("Новіша чернетка Єви");
  expect((await (await page.request.get(`${endpoint}/content`)).json()).resource.current_version_id).toBe(before.resource.current_version_id);
  await page.locator(".workspace-save-error").screenshot({ path: testInfo.outputPath("save-quota-en.png") });
  await page.getByRole("button", { name: "Save document", exact: true }).click();
  await expect(page.getByText("All document changes saved.", { exact: true })).toBeVisible();
  expect(requests[3].key).not.toBe(requests[2].key);
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("combobox", { name: "Interface language", exact: true }).selectOption("uk");
  await page.getByRole("button", { name: "Save language", exact: true }).click();
  await expect(page.getByRole("link", { name: "Профіль", exact: true })).toBeVisible();
  await cdp.detach();
});

test("one date fills outlined digit positions, undoes together, saves and reopens", async ({ page }) => {
  const { endpoint } = await open(page, "document");
  const editor = page.getByRole("textbox", {name:"Редагований документ",exact:true});
  const paragraph = editor.locator("p").first();
  async function selectDate() {
    await paragraph.click();
    await paragraph.evaluate(async node => {
      const changed = new Promise<void>(resolve => document.addEventListener("selectionchange", () => resolve(), {once:true}));
      window.getSelection()!.selectAllChildren(node); await changed;
    });
  }
  await selectDate();
  await page.keyboard.insertText("0 │ 1 │ 0 │ 1 │ 2 │ 0 │ 0 │ 0");
  await selectDate();
  await page.getByLabel("Дата в клітинках",{exact:true}).fill("2024-02-29");
  await page.getByRole("button",{name:"Заповнити вибрані клітинки дати",exact:true}).click();
  await expect(paragraph).toHaveText("2 │ 9 │ 0 │ 2 │ 2 │ 0 │ 2 │ 4");
  await page.getByRole("button",{name:"Скасувати",exact:true}).click();
  await expect(paragraph).toHaveText("0 │ 1 │ 0 │ 1 │ 2 │ 0 │ 0 │ 0");
  await page.getByRole("button",{name:"Повторити",exact:true}).click();
  await expect(paragraph).toHaveText("2 │ 9 │ 0 │ 2 │ 2 │ 0 │ 2 │ 4");
  await page.getByRole("button",{name:"Зберегти документ",exact:true}).click();
  await expect(page.getByText("Усі зміни документа збережено.",{exact:true})).toBeVisible();
  const saved = await (await page.request.get(`${endpoint}/content`)).json();
  const downloaded = await page.request.get(`${endpoint}/download`);
  expect(downloaded.status()).toBe(200);
  expect(downloaded.headers()["x-fillable-version"]).toBe(saved.resource.current_version_id);
  await page.reload();
  await expect(paragraph).toHaveText("2 │ 9 │ 0 │ 2 │ 2 │ 0 │ 2 │ 4");
});
