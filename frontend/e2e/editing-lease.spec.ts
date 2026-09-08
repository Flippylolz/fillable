import { manualSaving } from "./autosave-setting";
import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

async function savedContent(page: Page, identity: string) {
  let content: { document: unknown; resource: Record<string, unknown> } | undefined;
  await expect.poll(async () => {
    const response = await page.request.get(`/api/documents/${identity}/content`);
    if (response.status() === 409) {
      expect((await response.json()).error.code).toBe("operation_in_progress");
      return false;
    }
    expect(response.status()).toBe(200);
    const result = await response.json();
    expect(result.document).toBeDefined();
    expect(result.resource).toBeDefined();
    content = result;
    return true;
  }).toBe(true);
  return content!;
}

test("two tabs fence editing and preserve an IME draft, history and locale after lost access", async ({ page, context }, testInfo) => {
  await page.clock.install();
  await page.goto("/");
  await page.getByLabel("Логін", { exact: true }).fill(`lease-${testInfo.project.name}@example.test`);
  await page.getByLabel("Пароль", { exact: true }).fill("Synthetic-browser-Їжак-2026");
  await page.getByRole("button", { name: "Увійти", exact: true }).click();
  const title = `Доступ Їжака ${testInfo.project.name} ${randomUUID().slice(0, 8)}`;
  await page.getByLabel("Файл DOCX", { exact: true }).setInputFiles({ name: "Їжак.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: await readFile("/fixtures/upload.docx") });
  await page.getByLabel("Назва документа", { exact: true }).fill(title);
  await page.getByRole("button", { name: "Завантажити та зберегти", exact: true }).click();
  const acquisition = page.waitForResponse(response => response.url().endsWith("/editing-lease") && response.request().postDataJSON().action === "acquire");
  await page.getByRole("article", { name: title }).getByRole("link", { name: "Відкрити", exact: true }).click();
  const granted = await acquisition;
  expect(granted.status()).toBe(200);
  const holder = granted.request().postDataJSON(), generation = (await granted.json()).lease_id;
  const url = page.url(), identity = url.split("/").pop();
  await expect(page.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  await manualSaving(page);
  const values = page.getByRole("textbox", { name: "Значення поля: ПІБ клієнта", exact: true });
  await values.first().fill("Чернетка до паузи");
  const editor = page.getByRole("textbox", { name: "Редагований документ", exact: true });
  const sameEditor = await editor.elementHandle();
  const before = await savedContent(page, identity!);
  const usage = await (await page.request.get("/api/storage/usage")).json();
  const peer = await context.newPage();
  await peer.goto(url);
  await expect(peer.getByText("Цей документ редагують в іншій вкладці або сесії.", { exact: true })).toBeVisible();
  await expect(peer.getByRole("textbox", { name: "Редагований документ", exact: true })).toHaveAttribute("contenteditable", "false");
  const session = await (await page.request.get("/api/auth/session")).json();
  const release = async (body: object, leaseId: string) => {
    const response = await page.request.post(`/api/documents/${identity}/editing-lease`, {
      headers: { Origin: new URL(url).origin, "X-CSRF-Token": session.csrf_token }, data: { ...body, action: "release", lease_id: leaseId },
    });
    expect(response.status()).toBe(200);
  };
  await release(holder, generation);
  const peerAcquisition = peer.waitForResponse(response => response.url().endsWith("/editing-lease") && response.request().postDataJSON().action === "acquire");
  await peer.getByRole("button", { name: "Спробувати редагування знову", exact: true }).click();
  const peerGranted = await peerAcquisition;
  await expect(peer.getByText("Редагування дозволено.", { exact: true })).toBeVisible();
  // Lose authority during an existing native composition; keep and settle that draft.
  await page.getByRole("button", { name: "Перейти до поля: ПІБ клієнта", exact: true }).last().click();
  const cdp = await context.newCDPSession(page);
  const draft = "Їжак після паузи 🙂";
  await cdp.send("Input.imeSetComposition", { text: draft, selectionStart: draft.length, selectionEnd: draft.length });
  await page.clock.fastForward(21000);
  await expect(page.getByText("Редагування призупинено. Чернетка залишається в цьому робочому просторі.", { exact: true })).toBeVisible();
  await cdp.send("Input.insertText", { text: draft });
  await expect(values.first()).toHaveValue(draft);
  await expect(values.last()).toHaveValue(draft);
  await expect(editor).toHaveAttribute("contenteditable", "false");
  await expect(values.first()).toBeDisabled();
  await expect(page.getByRole("button", { name: "Скасувати", exact: true })).toBeDisabled();
  await editor.focus(); await page.keyboard.type("Blocked");
  await expect(editor).not.toContainText("Blocked");
  await page.locator(".workspace-access").screenshot({ path: testInfo.outputPath("lease-paused-uk.png") });
  await page.getByRole("link", { name: "Профіль", exact: true }).click();
  await page.getByRole("combobox", { name: "Мова інтерфейсу", exact: true }).selectOption("en");
  await page.getByRole("button", { name: "Зберегти мову", exact: true }).click();
  await page.getByRole("link", { name: "Document workspace", exact: true }).click();
  await expect(page.getByText("Editing is paused. Your draft is kept in this workspace.", { exact: true })).toBeVisible();
  await page.locator(".workspace-access").screenshot({ path: testInfo.outputPath("lease-paused-en.png") });
  await release(peerGranted.request().postDataJSON(), (await peerGranted.json()).lease_id);
  await peer.close();
  await page.getByRole("button", { name: "Try editing again", exact: true }).click();
  await expect(page.getByText("Editing enabled.", { exact: true })).toBeVisible();
  expect(await page.getByRole("textbox", { name: "Editable document", exact: true }).evaluate((node, retained) => node === retained, sameEditor)).toBe(true);
  await expect(page.getByRole("textbox", { name: "Field value: ПІБ клієнта", exact: true }).first()).toHaveValue(draft);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Field value: ПІБ клієнта", exact: true }).first()).toHaveValue("Чернетка до паузи");
  const after = await savedContent(page, identity!);
  expect(after.document).toEqual(before.document);
  expect(after.resource).toEqual({ ...before.resource, processing_status: after.resource.processing_status });
  expect(await (await page.request.get("/api/storage/usage")).json()).toEqual(usage);
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByRole("combobox", { name: "Interface language", exact: true }).selectOption("uk");
  await page.getByRole("button", { name: "Save language", exact: true }).click();
  await expect(page.getByRole("link", { name: "Профіль", exact: true })).toBeVisible();
  await cdp.detach();
});
